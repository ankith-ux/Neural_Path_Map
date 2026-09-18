import re

file1 = "/home/ankith/mahe_ws/frontend/src/components/Map/MapContainer.jsx"
file2 = "/home/ankith/mahe_ws/frontend (2)/src/components/Map/MapContainer.jsx"

with open(file1, 'r') as f1:
    content1 = f1.read()

with open(file2, 'r') as f2:
    content2 = f2.read()

# Extract from file2
start_marker = "    // --- NAVIGATION CAMERA CONTROLLER & CAR ANIMATION ---"
end_marker = "    const toggle3D = () => {"

start_idx2 = content2.find(start_marker)
end_idx2 = content2.find(end_marker)
block2 = content2[start_idx2:end_idx2]

start_idx1 = content1.find(start_marker)
end_idx1 = content1.find(end_marker)

new_content1 = content1[:start_idx1] + block2 + content1[end_idx1:]

with open(file1, 'w') as f1:
    f1.write(new_content1)

print("Applied nav patch")
