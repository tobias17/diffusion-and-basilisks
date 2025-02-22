from sklearn.cluster import KMeans
from scipy import stats
import numpy as np
import cv2, sys

QUANTIZE_COUNT = 4
VALUE_COUNT = 8
ASCII_CODEX = ' .:-=+*#@'

CHAR_HEIGHT = 16
CHAR_WIDTH  = 8
CHAR_ASPECT_RATIO = float(CHAR_HEIGHT) / float(CHAR_WIDTH)
TARGET_CHARS_TALL = 60

SCALE = [180.0, 255.0, 255.0]

def color(text:str, r:int, g:int, b:int) -> str:
   return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def hsv_to_bgr(mat):
   return cv2.cvtColor((mat * SCALE).astype(np.uint8), cv2.COLOR_HSV2BGR)

def image_to_ascii(filepath:str):
   bgr_img = cv2.imread(filepath)
   assert bgr_img is not None, f"Could not find input image, searched for {filepath}"

   hsv_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV) / SCALE

   to_circle = np.zeros((*hsv_img.shape[:2],2))
   to_circle[:,:,0] = np.cos(2*np.pi * hsv_img[:,:,0]) * hsv_img[:,:,1]
   to_circle[:,:,1] = np.sin(2*np.pi * hsv_img[:,:,0]) * hsv_img[:,:,1]

   kmeans = KMeans(n_clusters=QUANTIZE_COUNT)
   cluster_labels = kmeans.fit_predict(to_circle.reshape(-1,2))
   img_clusters = cluster_labels.reshape(hsv_img.shape[:2])

   centers = kmeans.cluster_centers_
   hs_selections = np.zeros((QUANTIZE_COUNT,2))
   hs_selections[:,0] = np.arctan2(centers[:,0], centers[:,1]) / (4*np.pi)
   hs_selections[:,0] = np.where(hs_selections[:,0] < 0.0, hs_selections[:,0] + 1.0, hs_selections[:,0])
   hs_selections[:,1] = np.sqrt(np.square(centers[:,0]), np.square(centers[:,1]))

   hsv_img[:,:,:2] = hs_selections[cluster_labels].reshape((*hsv_img.shape[:2],2))
   hsv_img[:,:,2] = (hsv_img[:,:,2] * VALUE_COUNT).astype(int) / VALUE_COUNT
   hsv_full = hsv_img.copy()
   hsv_full[:,:,2] = 0.6

   hsv_selections = np.ones((QUANTIZE_COUNT,3)) * 0.95
   hsv_selections[:,:2] = hs_selections
   print(hsv_selections)
   bgr_selections = hsv_to_bgr(hsv_selections.reshape((1,QUANTIZE_COUNT,3))).reshape((QUANTIZE_COUNT,3))

   bgr_img  = hsv_to_bgr(hsv_img)
   bgr_full = hsv_to_bgr(hsv_full)
   cv2.imwrite("tmp/quantized.png", bgr_img)
   cv2.imwrite("tmp/quantized_full.png", bgr_full)

   target_chars_wide = int(TARGET_CHARS_TALL * (bgr_img.shape[1] / bgr_img.shape[0]) * CHAR_ASPECT_RATIO)
   y_step = bgr_img.shape[0] / TARGET_CHARS_TALL
   x_step = bgr_img.shape[1] / target_chars_wide
   print(f"{x_step=} {y_step=} {target_chars_wide=} {TARGET_CHARS_TALL=}")

   small_patch_v = np.zeros((TARGET_CHARS_TALL,target_chars_wide))
   small_patch_hsv = np.ones((TARGET_CHARS_TALL,target_chars_wide,3))
   patched_hsv = np.zeros(bgr_img.shape)
   for yi in range(TARGET_CHARS_TALL):
      for xi in range(target_chars_wide):
         xs, xe = int(xi*x_step), int((xi+1)*x_step)
         ys, ye = int(yi*y_step), int((yi+1)*y_step)
         mode = stats.mode(img_clusters[ys:ye,xs:xe].flatten())
         patched_hsv[ys:ye,xs:xe,:2] = hs_selections[mode.mode]
         patched_hsv[ys:ye,xs:xe,2] = hsv_img[ys:ye,xs:xe,2].mean()
         small_patch_hsv[yi,xi,:2] = hs_selections[mode.mode]
         small_patch_v[yi,xi] = hsv_img[ys:ye,xs:xe,2].mean()
   cv2.imwrite("tmp/patched.png", hsv_to_bgr(patched_hsv))
   small_patch_bgr = hsv_to_bgr(small_patch_hsv)

   text = ""
   for y in range(TARGET_CHARS_TALL):
      for x in range(target_chars_wide):
         b, g, r = small_patch_bgr[y,x]
         c = ASCII_CODEX[int(small_patch_v[y,x] * len(ASCII_CODEX))]
         # c = "@"
         text += f"\033[38;2;{r};{g};{b}m{c}"
      text += "\n"
   text += "\033[0m"
   print(text, end="")
   sys.stdout.flush()

if __name__ == "__main__":
   image_to_ascii("tmp/image.png")
