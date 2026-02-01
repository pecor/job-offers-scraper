import csv
import io
import json
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from typing import Optional, List
from datetime import date, datetime
from app.database import get_db
from app.models import JobOffer
from app.schemas import JobOffer as JobOfferSchema
from pydantic import BaseModel

router = APIRouter()


class MarkSeenRequest(BaseModel):
    offer_ids: List[int]


class DeleteExpiredResponse(BaseModel):
    deleted_count: int


@router.get("/offers", response_model=List[JobOfferSchema])
async def get_offers(
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: Optional[int] = Query(0, ge=0),
    source: Optional[str] = None,
    show_seen: bool = Query(False, description="Show seen offers"),
    sort_by: str = Query("scraped_at", regex="^(scraped_at|valid_until|title|company)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    selected_technologies: Optional[str] = Query(None, description="Comma-separated list of technologies"),
    required_keywords: Optional[str] = Query(None, description="Comma-separated required keywords"),
    excluded_keywords: Optional[str] = Query(None, description="Comma-separated excluded keywords"),
    db: Session = Depends(get_db)
):
    """Get job offers with pagination and filters."""
    query = db.query(JobOffer)

    if source:
        query = query.filter(JobOffer.source == source)

    # Filter seen offers
    if not show_seen:
        query = query.filter(JobOffer.seen == False)

    if selected_technologies:
        tech_list = [tech.strip().lower() for tech in selected_technologies.split(',') if tech.strip()]
        if tech_list:
            tech_conditions = []
            for tech in tech_list:
                tech_conditions.append(JobOffer.technologies.ilike(f'%{tech}%'))
            if tech_conditions:
                query = query.filter(or_(*tech_conditions))

    if sort_by == "scraped_at":
        order_func = desc if sort_order == "desc" else asc
        query = query.order_by(order_func(JobOffer.scraped_at))
    elif sort_by == "valid_until":
        order_func = desc if sort_order == "desc" else asc
        query = query.order_by(order_func(JobOffer.valid_until))
    elif sort_by == "title":
        order_func = desc if sort_order == "desc" else asc
        query = query.order_by(order_func(JobOffer.title))
    elif sort_by == "company":
        order_func = desc if sort_order == "desc" else asc
        query = query.order_by(order_func(JobOffer.company))

    all_matching_offers = query.all()
    
    # Apply keyword filters in memory (for title, company, technologies only)
    if required_keywords or excluded_keywords:
        filtered_offers = []
        for offer in all_matching_offers:
            # Apply required keywords filter
            if required_keywords:
                required = [k.strip().lower() for k in required_keywords.split(',') if k.strip()]
                if required:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if not any(kw in search_text for kw in required):
                        continue
            
            # Apply excluded keywords filter
            if excluded_keywords:
                excluded = [k.strip().lower() for k in excluded_keywords.split(',') if k.strip()]
                if excluded:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if any(kw in search_text for kw in excluded):
                        continue
            
            filtered_offers.append(offer)
        all_matching_offers = filtered_offers
    
    # Apply pagination after filtering
    offers = all_matching_offers[offset:offset + limit]
    return offers


@router.get("/offers/{offer_id}", response_model=JobOfferSchema)
async def get_offer(offer_id: int, db: Session = Depends(get_db)):
    """Get single job offer."""
    offer = db.query(JobOffer).filter(JobOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.post("/offers/mark-seen")
async def mark_offers_seen(request: MarkSeenRequest, db: Session = Depends(get_db)):
    """Mark offers as seen."""
    updated = db.query(JobOffer).filter(JobOffer.id.in_(request.offer_ids)).update(
        {JobOffer.seen: True},
        synchronize_session=False
    )
    db.commit()
    return {"updated_count": updated}


@router.delete("/offers/delete-expired")
async def delete_expired_offers(db: Session = Depends(get_db)):
    """Delete expired job offers."""
    today = date.today()
    deleted = db.query(JobOffer).filter(JobOffer.valid_until < today).delete()
    db.commit()
    return {"deleted_count": deleted}


def convert_offer_to_dict(offer: JobOffer) -> dict:
    return {
        "id": offer.id,
        "url": offer.url,
        "title": offer.title,
        "company": offer.company,
        "location": offer.location,
        "description": offer.description,
        "technologies": offer.technologies,
        "salary_min": offer.salary_min,
        "salary_max": offer.salary_max,
        "salary_period": offer.salary_period,
        "work_type": offer.work_type,
        "contract_type": offer.contract_type,
        "employment_type": offer.employment_type,
        "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
        "source": offer.source,
        "seen": offer.seen,
        "scraped_at": offer.scraped_at.isoformat() if offer.scraped_at else None,
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
    }


class ExportRequest(BaseModel):
    offer_ids: list[int] = None
    export_all: bool = False
    source: str = None
    show_seen: bool = True
    sort_by: str = "scraped_at"
    sort_order: str = "desc"
    selected_technologies: list[str] = None
    required_keywords: str = None
    excluded_keywords: str = None


@router.post("/offers/export/json")
async def export_offers_json(request: ExportRequest, db: Session = Depends(get_db)):
    """Export offers as JSON. Can export selected offers, filtered offers, or all offers."""
    query = db.query(JobOffer)
    
    if request.offer_ids:
        # Export selected offers
        query = query.filter(JobOffer.id.in_(request.offer_ids))
    elif not request.export_all:
        # Apply filters (same as get_offers)
        if request.source:
            query = query.filter(JobOffer.source == request.source)
        if not request.show_seen:
            query = query.filter(JobOffer.seen == False)
        
        # Sorting
        if request.sort_by == "scraped_at":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.scraped_at))
        elif request.sort_by == "valid_until":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.valid_until))
        elif request.sort_by == "title":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.title))
        elif request.sort_by == "company":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.company))
    # else: export_all=True means no filters, get all offers
    
    offers = query.all()
    
    # Apply keyword filters in memory (for title, company, technologies only)
    if not request.export_all and request.offer_ids is None:
        filtered_offers = []
        for offer in offers:
            # Apply required keywords filter
            if request.required_keywords:
                required = [k.strip().lower() for k in request.required_keywords.split(',') if k.strip()]
                if required:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if not any(kw in search_text for kw in required):
                        continue
            
            # Apply excluded keywords filter
            if request.excluded_keywords:
                excluded = [k.strip().lower() for k in request.excluded_keywords.split(',') if k.strip()]
                if excluded:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if any(kw in search_text for kw in excluded):
                        continue
            
            filtered_offers.append(offer)
        offers = filtered_offers
    
    # Convert to dict format
    offers_data = [convert_offer_to_dict(offer) for offer in offers]
    
    json_str = json.dumps(offers_data, ensure_ascii=False, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=job_offers.json"}
    )


@router.post("/offers/export/csv")
async def export_offers_csv(request: ExportRequest, db: Session = Depends(get_db)):
    """Export offers as CSV. Can export selected offers, filtered offers, or all offers."""
    query = db.query(JobOffer)
    
    if request.offer_ids:
        # Export selected offers
        query = query.filter(JobOffer.id.in_(request.offer_ids))
    elif not request.export_all:
        # Apply filters (same as get_offers)
        if request.source:
            query = query.filter(JobOffer.source == request.source)
        if not request.show_seen:
            query = query.filter(JobOffer.seen == False)
        
        # Apply technology filter
        if request.selected_technologies:
            from sqlalchemy import or_
            tech_conditions = []
            for tech in request.selected_technologies:
                tech_lower = tech.lower()
                tech_conditions.append(JobOffer.technologies.ilike(f'%{tech_lower}%'))
            if tech_conditions:
                query = query.filter(or_(*tech_conditions))
        
        # Sorting
        if request.sort_by == "scraped_at":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.scraped_at))
        elif request.sort_by == "valid_until":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.valid_until))
        elif request.sort_by == "title":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.title))
        elif request.sort_by == "company":
            order_func = desc if request.sort_order == "desc" else asc
            query = query.order_by(order_func(JobOffer.company))
    # else: export_all=True means no filters, get all offers
    
    offers = query.all()
    
    # Apply keyword filters in memory (for title, company, technologies only)
    if not request.export_all and request.offer_ids is None:
        filtered_offers = []
        for offer in offers:
            # Apply required keywords filter
            if request.required_keywords:
                required = [k.strip().lower() for k in request.required_keywords.split(',') if k.strip()]
                if required:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if not any(kw in search_text for kw in required):
                        continue
            
            # Apply excluded keywords filter
            if request.excluded_keywords:
                excluded = [k.strip().lower() for k in request.excluded_keywords.split(',') if k.strip()]
                if excluded:
                    search_text = f"{offer.title or ''} {offer.company or ''} {offer.technologies or ''}".lower()
                    if any(kw in search_text for kw in excluded):
                        continue
            
            filtered_offers.append(offer)
        offers = filtered_offers
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "id", "url", "title", "company", "location", "description", "technologies",
        "salary_min", "salary_max", "salary_period", "work_type", "contract_type",
        "employment_type", "valid_until", "source", "seen", "scraped_at", "created_at"
    ])
    
    # Write data
    for offer in offers:
        writer.writerow([
            offer.id,
            offer.url,
            offer.title,
            offer.company or "",
            offer.location or "",
            offer.description or "",
            offer.technologies or "",
            offer.salary_min or "",
            offer.salary_max or "",
            offer.salary_period or "",
            offer.work_type or "",
            offer.contract_type or "",
            offer.employment_type or "",
            offer.valid_until.isoformat() if offer.valid_until else "",
            offer.source,
            offer.seen,
            offer.scraped_at.isoformat() if offer.scraped_at else "",
            offer.created_at.isoformat() if offer.created_at else "",
        ])
    
    output.seek(0)
    return Response(
        content=output.getvalue().encode('utf-8-sig'),  # BOM for Excel compatibility
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_offers.csv"}
    )


@router.post("/offers/import/json")
async def import_offers_json(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import offers from JSON file."""
    try:
        content = await file.read()
        offers_data = json.loads(content.decode('utf-8'))
        
        imported_count = 0
        skipped_count = 0
        
        for offer_data in offers_data:
            url = offer_data.get('url')
            if not url:
                skipped_count += 1
                continue
            
            # Check if offer already exists
            existing = db.query(JobOffer).filter(JobOffer.url == url).first()
            if existing:
                skipped_count += 1
                continue
            
            # Parse dates
            valid_until = None
            if offer_data.get('valid_until'):
                try:
                    valid_until = datetime.fromisoformat(offer_data['valid_until'].replace('Z', '+00:00')).date()
                except:
                    try:
                        valid_until = datetime.strptime(offer_data['valid_until'], '%Y-%m-%d').date()
                    except:
                        pass
            
            scraped_at = None
            if offer_data.get('scraped_at'):
                try:
                    scraped_at = datetime.fromisoformat(offer_data['scraped_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            created_at = None
            if offer_data.get('created_at'):
                try:
                    created_at = datetime.fromisoformat(offer_data['created_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            offer = JobOffer(
                url=url,
                title=offer_data.get('title', ''),
                company=offer_data.get('company'),
                location=offer_data.get('location'),
                description=offer_data.get('description'),
                technologies=offer_data.get('technologies'),
                salary_min=offer_data.get('salary_min'),
                salary_max=offer_data.get('salary_max'),
                salary_period=offer_data.get('salary_period'),
                work_type=offer_data.get('work_type'),
                contract_type=offer_data.get('contract_type'),
                employment_type=offer_data.get('employment_type'),
                valid_until=valid_until,
                source=offer_data.get('source', 'imported'),
                seen=offer_data.get('seen', False),
                scraped_at=scraped_at,
                created_at=created_at,
            )
            db.add(offer)
            imported_count += 1
        
        db.commit()
        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "message": f"Zaimportowano {imported_count} ofert, pominięto {skipped_count} (duplikaty lub brak URL)"
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format JSON")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd podczas importu: {str(e)}")


@router.post("/offers/import/csv")
async def import_offers_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import offers from CSV file."""
    try:
        content = await file.read()
        content_str = content.decode('utf-8-sig')  # Handle BOM
        csv_reader = csv.DictReader(io.StringIO(content_str))
        
        imported_count = 0
        skipped_count = 0
        
        for row in csv_reader:
            url = row.get('url', '').strip()
            if not url:
                skipped_count += 1
                continue
            
            # Check if offer already exists
            existing = db.query(JobOffer).filter(JobOffer.url == url).first()
            if existing:
                skipped_count += 1
                continue
            
            # Parse dates
            valid_until = None
            if row.get('valid_until'):
                try:
                    valid_until = datetime.fromisoformat(row['valid_until']).date()
                except:
                    try:
                        valid_until = datetime.strptime(row['valid_until'], '%Y-%m-%d').date()
                    except:
                        pass
            
            scraped_at = None
            if row.get('scraped_at'):
                try:
                    scraped_at = datetime.fromisoformat(row['scraped_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            created_at = None
            if row.get('created_at'):
                try:
                    created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                except:
                    pass
            
            # Parse boolean
            seen = row.get('seen', 'False').lower() in ('true', '1', 'yes')
            
            # Parse floats
            salary_min = None
            if row.get('salary_min'):
                try:
                    salary_min = float(row['salary_min'])
                except:
                    pass
            
            salary_max = None
            if row.get('salary_max'):
                try:
                    salary_max = float(row['salary_max'])
                except:
                    pass
            
            offer = JobOffer(
                url=url,
                title=row.get('title', ''),
                company=row.get('company') or None,
                location=row.get('location') or None,
                description=row.get('description') or None,
                technologies=row.get('technologies') or None,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_period=row.get('salary_period') or None,
                work_type=row.get('work_type') or None,
                contract_type=row.get('contract_type') or None,
                employment_type=row.get('employment_type') or None,
                valid_until=valid_until,
                source=row.get('source', 'imported'),
                seen=seen,
                scraped_at=scraped_at,
                created_at=created_at,
            )
            db.add(offer)
            imported_count += 1
        
        db.commit()
        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "message": f"Zaimportowano {imported_count} ofert, pominięto {skipped_count} (duplikaty lub brak URL)"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd podczas importu: {str(e)}")
