from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.contacts import router as contacts_router
from app.api.routes.failover import router as failover_router
from app.api.routes.incoming import router as incoming_router
from app.api.routes.modems import router as modems_router
from app.api.routes.node import router as node_router
from app.api.routes.queue import router as queue_router
from app.api.routes.reports import router as reports_router
from app.api.routes.rules import router as rules_router
from app.api.routes.sms import router as sms_router
from app.api.routes.templates import router as templates_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(contacts_router)
api_router.include_router(failover_router)
api_router.include_router(templates_router)
api_router.include_router(campaigns_router)
api_router.include_router(rules_router)
api_router.include_router(queue_router)
api_router.include_router(incoming_router)
api_router.include_router(modems_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(node_router)
api_router.include_router(sms_router)
