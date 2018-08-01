import numpy as np
import cv2

import align


class _Transf:
  def __init__(self, s, A, b):
    self._s = s
    self._A = A
    self._b = b

  def __call__(self, x):
    return self._s * np.dot(x, self._A.T) + self._b


def _find_alignments(all_imgs, all_pts):
  # find alignment between first and every other image
  img1 = all_imgs[0]
  transfs = []
  for i, img2 in enumerate(all_imgs[1:]):
    # find minimum mse alignment iteratively
    A, b, s = align.iterative(img1, all_pts[0], img2, all_pts[i + 1])

    # create mapping from img1 coordinates to img2 coordinates
    transfs.append(_Transf(s, A, b))

  return transfs


def _compute_valid_region(all_imgs, transfs, patch_size):
  # find patches in img1 that are in all images
  img1 = all_imgs[0]
  valid = np.ones_like(img1, dtype=np.bool)
  half = patch_size // 2
  for k, img2 in enumerate(all_imgs[1:]):
    # find pixels in both img1 and img2
    aligned = np.zeros_like(img1, dtype=np.bool)
    for i in range(half, valid.shape[0] - half):
      for j in range(half, valid.shape[1] - half):
        row, col = transfs[k]((i, j))
        row = int(np.round(row))
        col = int(np.round(col))
        if 0 <= row - half < img2.shape[0] and 0 <= row + half < img2.shape[0]:
          if 0 <= col - half < img2.shape[1] and 0 <= col + half < img2.shape[1]:
            aligned[i, j] = True

    # update overall valid positions
    valid = np.logical_and(valid, aligned)

  return valid


class Handler:
  def __init__(self, all_imgs, all_pts, patch_size, flip=False,
               for_sift=False):
    self._flip = flip
    self._imgs = all_imgs
    self._patch_size = patch_size
    self._half = patch_size // 2

    # align all images to the first
    self._transfs = _find_alignments(self._imgs, all_pts)

    # find valid area for extracting patches
    mask = _compute_valid_region(self._imgs, self._transfs, self._patch_size)

    # adjust images for sift patches
    if for_sift:
      clahe = cv2.createCLAHE(clipLimit=3)
      for i, img in enumerate(self._imgs):
        img = np.array(255 * img, dtype=np.uint8)
        img = cv2.medianBlur(img, ksize=3)
        img = clahe.apply(img)
        self._imgs[i] = np.array(img, dtype=np.float32) / 255

    # get valid indices and store them for access
    self._inds = []
    if self._flip:
      # augment with flips
      for pt in all_pts[0]:
        if mask[pt[0], pt[1]]:
          self._inds.append((0, pt))
          self._inds.append((1, pt))
    else:
      for pt in all_pts[0]:
        if mask[pt[0], pt[1]]:
          self._inds.append((0, pt))

  def __getitem__(self, val):
    if isinstance(val, slice):
      raise TypeError('Slicing indexing is not supported')
    else:
      # retrieve coordinates for given index
      flip, (i, j) = self._inds[val]

      # adjust for odd patch sizes
      odd = 1 if self._patch_size % 2 != 0 else 0

      # add first image patch
      samples = [
          self._imgs[0][i - self._half:i + self._half + odd, j - self._half:
                        j + self._half + odd]
      ]

      # add remaining image patches
      for k, img in enumerate(self._imgs[1:]):
        # find transformed coordinates of patch
        ti, tj = self._transfs[k]((i, j))

        # convert them to int
        ti = int(np.round(ti))
        tj = int(np.round(tj))

        # add to overall
        samples.append(img[ti - self._half:ti + self._half + odd,
                           tj - self._half:tj + self._half + odd])

    # augment with flip
    if self._flip and flip != 0:
      samples = np.flip(samples, axis=flip)

    return np.array(samples)

  def __len__(self):
    if self._flip:
      return 2 * len(self._inds)

    return len(self._inds)
