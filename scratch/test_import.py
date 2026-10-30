import time

t0 = time.time()
print("1. importing nl_extractor...")
from backend.app.interface.nl_extractor import NaturalLanguageExtractor
print(f"   done in {time.time()-t0:.2f}s")

t0 = time.time()
print("2. importing main...")
import backend.main as main
print(f"   done in {time.time()-t0:.2f}s")
