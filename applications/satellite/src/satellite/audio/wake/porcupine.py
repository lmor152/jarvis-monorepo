from typing import Sequence

import pvporcupine


class PorcupineWakeWord:
    def __init__(
        self, keywords: Sequence[str], sensitivities: Sequence[float], access_key: str
    ) -> None:
        self.porcupine: pvporcupine.Porcupine = pvporcupine.create(
            keywords=keywords,
            sensitivities=sensitivities,
            access_key=access_key,
        )

    def process(self, pcm):
        return self.porcupine.process(pcm)

    def delete(self):
        self.porcupine.delete()
