"""Development-only local IP restriction recovery; no HTTP bypass or account changes."""
import argparse
from sqlalchemy import select
from app.core.config import settings
from app.database.store import begin_security_transaction, configure
from app.models.entities import SuspiciousIP
from app.security.ip import canonical_ip
from app.services.ips import unblock_ip


def recover(factory,address,note,*,environment,confirmed=False):
    if environment!='development':
        raise PermissionError('Local recovery is allowed only in development')
    if not confirmed or not 3<=len(note.strip())<=500:
        raise ValueError('Use explicit confirmation and a note of 3–500 characters')
    address=canonical_ip(address)
    with factory() as db:
        begin_security_transaction(db)
        ip=db.scalar(select(SuspiciousIP).where(SuspiciousIP.address==address))
        if not ip:
            raise ValueError('No record for this IP address')
        changed=unblock_ip(db,ip,note=note.strip(),actor='development_cli')
        db.commit()
    return changed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip',required=True)
    parser.add_argument('--note',required=True)
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if settings.protocolguard_env!='development':
        parser.exit(2,'Local recovery is allowed only in development\n')
    engine,factory=configure(settings.database_url)
    try:
        changed=recover(factory,args.ip,args.note,environment=settings.protocolguard_env,confirmed=args.confirm)
        print('IP restriction released' if changed else 'IP was already unrestricted')
    except (ValueError,PermissionError) as error:
        parser.exit(2,str(error)+'\n')
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
