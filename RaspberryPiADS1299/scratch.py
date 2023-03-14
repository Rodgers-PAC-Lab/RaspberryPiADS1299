import matplotlib.pyplot as plt

parsed = [
    [-131072, 6815603, 2621292, 6815602, -149, -147, 7864176, -6291599],
    [-4510, -4727, -4513, -4729, -4700, -4586, -4551, -4514],
    [-4519, -4720, -4516, -4740, -4692, -4591, -4541, -4511],
    [-4516, -4731, -4517, -4742, -4694, -4591, -4541, -4531],
    [-4521, -4732, -4521, -4740, -4697, -4595, -4535, -4524]
]
plt.plot(parsed)
# plt.show()

speeds = {
        '0x90': '16k SPS = every 0.0000625 seconds',
        '0x91': '8k SPS = every 0.000125 seconds',
        '0x92': '4k SPS = every 0.00025 seconds',
        '0x93': '2k SPS = every 0.0005 seconds',
        '0x94': '1k SPS = every 0.001 seconds',
        '0x95': '500 SPS = every 0.002 seconds',
        '0x96': '250 SPS = every 0.004 seconds'
        }
