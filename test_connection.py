# test_connection.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
import os

async def test_mongodb():
    """Testa conexão com MongoDB Atlas"""
    mongodb_url = "mongodb://plablo:<db_password>@ac-zgmviop-shard-00-00.t0ozb1f.mongodb.net:27017,ac-zgmviop-shard-00-01.t0ozb1f.mongodb.net:27017,ac-zgmviop-shard-00-02.t0ozb1f.mongodb.net:27017/?ssl=true&replicaSet=atlas-y77oa6-shard-0&authSource=admin&appName=Cluster0"
    
    try:
        client = AsyncIOMotorClient(mongodb_url)
        await client.admin.command('ping')
        print("✅ MongoDB Atlas: CONECTADO com sucesso!")
        return True
    except Exception as e:
        print(f"❌ MongoDB Atlas: ERRO - {str(e)}")
        return False

async def test_zapi():
    """Testa conexão com Z-API"""
    instance_id = "3F43467A7F5BF175DDAF66DA177DAE5D"
    token = "7B297D6399C13767601B1C78"
    url = f"https://api.z-api.io/instances/{instance_id}/token/{token}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/status")
            if response.status_code == 200:
                print("✅ Z-API: CONECTADA com sucesso!")
                return True
            else:
                print(f"⚠️ Z-API: Status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Z-API: ERRO - {str(e)}")
        return False

async def main():
    print("\n🔍 Testando conexões...\n")
    mongodb_ok = await test_mongodb()
    zapi_ok = await test_zapi()
    
    print("\n📊 RESULTADO FINAL:")
    print(f"MongoDB Atlas: {'✅ OK' if mongodb_ok else '❌ FALHA'}")
    print(f"Z-API: {'✅ OK' if zapi_ok else '❌ FALHA'}")
    
    if mongodb_ok and zapi_ok:
        print("\n🎉 Tudo pronto! Sistema pode ser iniciado.")
    else:
        print("\n⚠️ Verifique as configurações e tente novamente.")

if __name__ == "__main__":
    asyncio.run(main())