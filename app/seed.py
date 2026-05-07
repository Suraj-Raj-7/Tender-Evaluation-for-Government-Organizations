from sqlalchemy.orm import Session as SASession
from app.models import User, Role
from app.security import hash_password

def run_seed(db: SASession):
    if db.query(User).count() > 0:
        return
    
    users = [
        ("admin", "System Administrator", "Admin@123", Role.EVALUATOR),
        ("bidder1", "Bharat Construction", "Bidder@123", Role.BIDDER),
        ("auditor1", "Internal Auditor", "Auditor@123", Role.AUDITOR),
    ]
    
    for u, fn, pw, r in users:
        db.add(User(
            username=u, 
            full_name=fn, 
            password_hash=hash_password(pw), 
            role=r
        ))
    db.commit()
    print("Default users seeded: admin, bidder1, auditor1")