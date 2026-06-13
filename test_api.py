import os
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"
IMAGE_PATH = "/Users/josetaneo/.gemini/antigravity-cli/brain/a8a75bd1-44b2-49af-b7bf-04e2712c3e40/test_face_1_1781346964476.jpg"

def run_tests():
    print("🚀 Memulai Pengujian API FaceID-KP...")

    # 1. Test Home/Dashboard
    try:
        res = requests.get(BASE_URL + "/")
        print(f"[GET /] Status: {res.status_code}")
        assert res.status_code == 200
    except Exception as e:
        print(f"Error accessing Home: {e}")
        sys.exit(1)

    # 2. Test Register API
    print("\n[TEST] Registrasi Wajah...")
    with open(IMAGE_PATH, "rb") as f1, open(IMAGE_PATH, "rb") as f2, open(IMAGE_PATH, "rb") as f3:
        files = [
            ("files", ("frame1.jpg", f1, "image/jpeg")),
            ("files", ("frame2.jpg", f2, "image/jpeg")),
            ("files", ("frame3.jpg", f3, "image/jpeg")),
        ]
        data = {
            "full_name": "Test User AI",
            "gender": "Wanita",
            "phone_number": "081234567890"
        }
        res = requests.post(BASE_URL + "/api/register", data=data, files=files)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        if res.status_code == 400 and "sudah terdaftar" in res.json().get("message", ""):
            print("User is already registered from a previous test. Continuing...")
        else:
            assert res.status_code == 200

    # 3. Test Recognize API (Valid Location)
    print("\n[TEST] Absensi Wajah (Lokasi Valid)...")
    with open(IMAGE_PATH, "rb") as f:
        files = {"file": ("capture.jpg", f, "image/jpeg")}
        data = {
            "lat": -7.979261, # GKI Bromo lat
            "lng": 112.625760 # GKI Bromo lng
        }
        res = requests.post(BASE_URL + "/api/recognize", data=data, files=files)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200

    # 4. Test Recognize API (Invalid Location)
    print("\n[TEST] Absensi Wajah (Lokasi Tidak Valid - Jakarta)...")
    with open(IMAGE_PATH, "rb") as f:
        files = {"file": ("capture.jpg", f, "image/jpeg")}
        data = {
            "lat": -6.200000, # Jakarta
            "lng": 106.816666 # Jakarta
        }
        res = requests.post(BASE_URL + "/api/recognize", data=data, files=files)
        print(f"Status Code: {res.status_code}")
        try:
            print(f"Response: {res.json()}")
        except:
            print(res.text)
        assert res.status_code == 403

    # 5. Test Export Excel
    print("\n[TEST] Export Excel...")
    res = requests.get(BASE_URL + "/api/analytics/export?period=today")
    print(f"Status Code: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    assert res.status_code == 200
    assert "excel" in res.headers.get("content-type", "").lower()

    print("\n✅ Semua pengujian berhasil dilewati!")

if __name__ == "__main__":
    run_tests()
