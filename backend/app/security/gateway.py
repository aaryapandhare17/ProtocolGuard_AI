"""ASGI gateway: reject blocked IPs before authentication or route execution."""
import json
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from app.database.store import begin_security_transaction, now
from app.models.entities import SecurityEvent,SuspiciousIP
from app.security.ip import connection_ip
from app.security.proxy_ip import signing_secret, verified_client_ip
from app.services.ips import active_restriction


class IPGateway:
    def __init__(self,app,factory,config):
        self.app,self.factory,self.config=app,factory,config
        self.proxy_secret=signing_secret(config)

    def check(self,address,path):
        # Database lock waits must not block the ASGI event loop.
        with self.factory() as db:
            begin_security_transaction(db)
            restriction=active_restriction(db,address)
            if restriction:
                ip=db.get(SuspiciousIP,restriction.ip_id)
                ip.last_seen=now()
                db.add(SecurityEvent(ip=address,event_type='ACCESS_BLOCKED',endpoint=path,outcome='denied',
                    evidence=json.dumps({'scope':'gateway','entity':'ip','restriction_id':restriction.id})))
            denied=bool(restriction)
            db.commit()
            return denied

    async def __call__(self,scope,receive,send):
        if scope['type'] not in {'http','websocket'} or (scope.get('path')=='/api/health' and scope.get('method')=='GET'):
            return await self.app(scope,receive,send)
        if self.config.require_signed_client_ip and scope['type']=='websocket':
            return await send({'type':'websocket.close','code':4403})
        try:
            verified=verified_client_ip(scope,self.proxy_secret)
            if self.config.require_signed_client_ip and scope['type']=='http' and scope.get('path','').startswith('/api/') and scope.get('method')!='OPTIONS' and not verified:
                raise ValueError('Signed visitor address required')
        except ValueError:
            return await JSONResponse({'detail':'Invalid signed visitor address'},status_code=400)(scope,receive,send)
        address=verified or connection_ip(scope)
        if not address:
            return await self.app(scope,receive,send)
        scope={**scope,'client':(address,scope['client'][1] if scope.get('client') else 0)}
        denied=await run_in_threadpool(self.check,address,scope['path'])
        if not denied:
            return await self.app(scope,receive,send)
        if scope['type']=='websocket':
            return await send({'type':'websocket.close','code':4403})
        origin=dict(scope.get('headers',[])).get(b'origin',b'').decode('latin1')
        headers={}
        if origin in self.config.cors_origins.split(','):
            headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Credentials':'true','Vary':'Origin'}
        response=JSONResponse({'detail':'IP access restricted'},status_code=403,headers=headers)
        return await response(scope,receive,send)
