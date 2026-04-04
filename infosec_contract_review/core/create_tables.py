"""Create all tables directly from SQLAlchemy models (dev shortcut)."""
from infosec_contract_review.models.base import Base
from infosec_contract_review.core.database import engine
# Ensure all models are imported so Base.metadata is complete
import infosec_contract_review.models  # noqa: F401


def create_all():
    Base.metadata.create_all(bind=engine)
    print("All tables created.")


if __name__ == "__main__":
    create_all()
