import os

model_path = os.path.abspath("static/models/best.pt")
print("Đường dẫn tuyệt đối:", model_path)

print("Tệp tồn tại?", os.path.exists(model_path))