def equation(strain, temp, params):
    sat = params[0] + params[1] * temp + params[6] * temp ** 2
    k = params[2] * (1 + params[7] * temp)
    soft = (params[3] + params[4] * temp) * np.abs(strain) ** params[5]
    return sat * (1 - np.exp(-k * strain)) - soft
