from fastapi import APIRouter

router = APIRouter(
    prefix="/omnibooker",
    tags=["omnibooker"],
    responses={404: {"description": "Not found"}},
)


@router.get("/book-tennis-court")
async def book_tennis_court():
    raise NotImplementedError("This endpoint is not yet implemented")


@router.get("/check-availability")
async def check_availability():
    raise NotImplementedError("This endpoint is not yet implemented")
