from backend.router import compute_blended_rank

print("SUV route 1:")
print(compute_blended_rank(384, 81.03, 0.4, use_vehicle_score=True, vehicle_score=44.76))

print("SUV route 2:")
print(compute_blended_rank(377, 86.85, 0.4, use_vehicle_score=True, vehicle_score=53.84))

print("SUV route 3:")
print(compute_blended_rank(358, 84.2, 0.4, use_vehicle_score=True, vehicle_score=53.93))
