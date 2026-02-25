import numpy as np
from scipy.io import loadmat
import matplotlib.pyplot as plt

grain_py = np.load("verification/specrogram_engine_bbn/grain_block0_python.npz")["grain"]
grain_mat = loadmat("verification/specrogram_engine_bbn/grain_block1_matlab.mat")["Grain"].squeeze()

plt.plot(grain_py, label="Python")
plt.plot(grain_mat, label="MATLAB", linestyle='--')
plt.title("Grain Block 0 - Python vs MATLAB")
plt.legend()
plt.grid(True)
plt.show()
