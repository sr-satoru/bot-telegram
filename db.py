"""
Módulo do cliente Prisma — singleton compartilhado por todos os módulos.

Uso:
    from db import prisma

    # No startup do bot:
    await prisma.connect()

    # No shutdown:
    await prisma.disconnect()
"""

from prisma import Prisma

prisma = Prisma()
