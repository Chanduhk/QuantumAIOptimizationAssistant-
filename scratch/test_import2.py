import time
t0 = time.time()
print("Importing test_f15_natural_language_planning...")
import backend.tests.test_f15_natural_language_planning as t
print(f"Imported in {time.time()-t0:.2f}s")
print("Functions in module:", [f for f in dir(t) if f.startswith("test_")])
