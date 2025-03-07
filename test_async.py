import asyncio

async def test_func():
    await asyncio.sleep(0.1)
    return "Hello"

print(f"Is test_func async? {asyncio.iscoroutinefunction(test_func)}")

async def main():
    result = await test_func()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())