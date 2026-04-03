import asyncio
from bleak import BleakClient

ADDRESS = "10:52:1C:5F:BE:EA"  # your current address

async def main():
    async with BleakClient(ADDRESS) as client:
        print(f"Connected: {client.is_connected}")
        for service in client.services:
            print(f"\nService: {service.uuid}")
            for char in service.characteristics:
                print(f"  Characteristic: {char.uuid}")
                print(f"    Properties: {char.properties}")

asyncio.run(main())