import numpy as np


def get_emission_angle(input_data):
    """Extract PANAM emission angles (phix, phiy) across all time steps."""
    n = len(input_data)
    phix = np.array([input_data[i]['phix'] for i in range(n)])
    phiy = np.array([input_data[i]['phiy'] for i in range(n)])
    return {"phix": phix, "phiy": phiy}
