import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis

class FaceService:
    def __init__(self):
        # Kita pakai model 'buffalo_l' (Large) untuk akurasi maksimal. 
        # Kalau laptop terasa berat, ganti 'buffalo_l' jadi 'buffalo_sc' (Small/Fast).
        print("⏳ Loading AI Models... (Mungkin agak lama di run pertama)")
        self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        
        # ctx_id=0 artinya pakai GPU pertama (jika ada), kalau tidak ada dia fallback ke CPU
        # det_size=(640, 640) adalah resolusi deteksi.
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        print("✅ AI Models Loaded!")

    def get_embedding(self, image_bytes):
        """
        Menerima bytes gambar, mengembalikan vector (list of float)
        """
        # Convert bytes ke format yang bisa dibaca OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Gambar tidak valid")

        # Deteksi wajah & ekstrak fitur
        faces = self.app.get(img)

        if len(faces) == 0:
            return None # Tidak ada wajah terdeteksi
        
        # Ambil wajah dengan area terbesar (asumsi itu user yang mau absen)
        # Kita sort berdasarkan luas kotak wajah (bbox)
        largest_face = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0]) * (x.bbox[3]-x.bbox[1]), reverse=True)[0]
        
        # Return embedding (vector 512 dimensi)
        # Kita harus convert numpy array ke list python biasa agar bisa masuk JSON
        return largest_face.embedding.tolist()

# Singleton instance (supaya model tidak di-load berulang kali setiap request)
face_service = FaceService()