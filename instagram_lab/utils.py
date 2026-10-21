import time
import random

def random_pause(min_s: float = 0.3, max_s: float = 0.8):
    time.sleep(random.uniform(min_s, max_s))