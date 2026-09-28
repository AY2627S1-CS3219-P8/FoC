from alembic import context
from sqlalchemy import create_engine, MetaData, pool

from app.config import Settings


def load_target_metadata() -> MetaData:
    import app.models
    from app.db import Base

    return Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table" and name == "spatial_ref_sys" and reflected:
        return False

    return True

def run_migrations_offline(settings: Settings, metadata: MetaData) -> None:
    context.configure(
        url=str(settings.database_url),
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online(settings: Settings, metadata: MetaData) -> None:
    # Create a synchronous SQLAlchemy engine using the settings URL and
    # pool.NullPool: this short-lived migration process needs no retained pool.
    engine = create_engine(str(settings.database_url), poolclass=pool.NullPool)

    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata, include_object=include_object)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()

def main() -> None:
    settings = Settings()
    metadata = load_target_metadata()

    if context.is_offline_mode():
        run_migrations_offline(settings, metadata)
    else:
        run_migrations_online(settings, metadata)

main()
