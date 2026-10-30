import time
t0 = time.time()
print("1. Mocking VectorMemorySystem...")
from backend.app.memory.vector_memory import VectorMemorySystem
VectorMemorySystem._load_model = lambda self: None
VectorMemorySystem.preload_model_async = lambda model_name="all-MiniLM-L6-v2": None
print(f"   Mocked in {time.time()-t0:.2f}s")

t1 = time.time()
print("2. Importing backend.main...")
import backend.main as main
print(f"   Done in {time.time()-t1:.2f}s")
