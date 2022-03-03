import numpy as np

with open("./tests/testrandom", 'w') as f:
    for i in range(1000):
        f.write(f"{np.random.randint(0, 9999)}\n")
