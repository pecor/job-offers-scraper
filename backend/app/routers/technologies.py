from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import JobOffer

router = APIRouter()


@router.get("/technologies")
async def get_technologies(db: Session = Depends(get_db)):
    offers = db.query(JobOffer).filter(JobOffer.technologies.isnot(None)).all()
    
    all_techs = set()
    for offer in offers:
        if offer.technologies:
            techs = [t.strip() for t in offer.technologies.split(',') if t.strip()]
            all_techs.update(techs)
    
    return sorted(list(all_techs))
