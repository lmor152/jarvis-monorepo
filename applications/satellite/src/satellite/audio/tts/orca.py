import queue
import threading
from typing import Callable, Optional, Union, cast

import numpy as np
import pvorca  # type: ignore
import sounddevice as sd  # type: ignore

OnComplete = Optional[Callable[[], None]]
QueuePayload = tuple[str, OnComplete]
QueueItem = Union[QueuePayload, object]


_SENTINEL = object()


class OrcaTTS:
    """Non-blocking streaming text-to-speech using Picovoice Orca."""

    def __init__(self, access_key: str, *, output_device: int | str | None = None):
        self.orca = pvorca.create(access_key=access_key)
        self.sample_rate = self.orca.sample_rate
        self.output_device = output_device

        # Threading & queue for background playback
        self.queue: queue.Queue[QueueItem] = queue.Queue()
        self.playing = False
        self.stop_flag = threading.Event()
        self.current_callback: OnComplete = None

        # Start playback worker
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def speak(self, text: str, on_complete: OnComplete = None):
        """Queue text to speak asynchronously."""
        print("🗣️ Queuing TTS:", text)
        self.queue.put((text, on_complete))

    def stop(self):
        """Stop playback immediately and clear any queued messages."""
        self.stop_flag.set()
        self._clear_pending()

    def _clear_pending(self):
        """Remove all queued items so new speech can begin fresh."""
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            else:
                if item is _SENTINEL:
                    self.queue.put_nowait(_SENTINEL)
                    break
                self.queue.task_done()

    def _worker(self):
        """Background worker that continuously plays queued TTS messages."""
        while True:
            item = self.queue.get()
            if item is _SENTINEL:
                self.queue.task_done()
                break  # Graceful shutdown

            text, callback = cast(QueuePayload, item)
            self.playing = True
            self.stop_flag.clear()
            self.current_callback = callback
            interrupted = False

            try:
                audio, _ = self.orca.synthesize(text)

                if isinstance(audio, (bytes, bytearray, memoryview)):
                    pcm_int16 = np.frombuffer(audio, dtype=np.int16)
                else:
                    pcm_int16 = np.asarray(audio, dtype=np.int16)

                pcm: np.ndarray = pcm_int16.astype(np.float32) / 32768.0

                chunk_size = 2048
                stream_kwargs: dict[str, object] = {
                    "samplerate": self.sample_rate,
                    "channels": 1,
                    "dtype": "float32",
                    "blocksize": chunk_size,
                }
                if self.output_device is not None:
                    stream_kwargs["device"] = self.output_device

                with sd.OutputStream(
                    **stream_kwargs,
                ) as stream:
                    for i in range(0, len(pcm), chunk_size):
                        if self.stop_flag.is_set():
                            interrupted = True
                            try:
                                stream.abort()
                            except Exception:
                                pass
                            break

                        chunk = pcm[i : i + chunk_size]
                        stream.write(chunk.reshape(-1, 1))  # type: ignore[misc]

            except Exception as e:
                print("TTS error:", e)
                interrupted = True

            finally:
                if not interrupted and self.current_callback:
                    try:
                        self.current_callback()
                    except Exception as callback_error:
                        print("TTS completion callback error:", callback_error)

                self.current_callback = None
                self.playing = False
                self.stop_flag.clear()
                self.queue.task_done()

        # Drain any remaining items to unblock producers before exit
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break

    def delete(self):
        """Gracefully shut down TTS thread and release resources."""
        self.queue.put(_SENTINEL)
        self.thread.join(timeout=2)
        self.orca.delete()
