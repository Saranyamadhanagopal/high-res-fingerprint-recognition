from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from six.moves import range

import numpy as np

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
    for i in range(valid.shape[0] - patch_size + 1):
      for j in range(valid.shape[1] - patch_size + 1):
        row, col = transfs[k]((i + half, j + half))
        row = int(np.round(row))
        col = int(np.round(col))
        if 0 <= row - half < img2.shape[0] and 0 <= row + half < img2.shape[0]:
          if 0 <= col - half < img2.shape[1] and 0 <= col + half < img2.shape[1]:
            aligned[i, j] = True

    # update overall valid positions
    valid = np.logical_and(valid, aligned)

  return valid


class Handler:
  def __init__(self, all_imgs, all_pts, patch_size):
    self._imgs = all_imgs
    self._patch_size = patch_size
    self._half = patch_size // 2

    # align all images to the first
    self._transfs = _find_alignments(self._imgs, all_pts)

    # find valid area for extracting patches
    mask = _compute_valid_region(self._imgs, self._transfs, self._patch_size)

    # get valid indices and store them for access
    self._inds = np.argwhere(mask)

  def __getitem__(self, val):
    if isinstance(val, slice):
      samples = []
      for i, j in self._inds[val]:
        # add first image patch
        sample = [
            self._imgs[0][i:i + self._patch_size, j:j + self._patch_size]
        ]

        # add remaining image patches
        for k, img in enumerate(self._imgs[1:]):
          # find transformed coordinates of patch
          ti, tj = self._transfs[k]((i + self._half, j + self._half))

          # convert them to int
          ti = int(np.round(ti))
          tj = int(np.round(tj))

          # add to index overall
          sample.append(img[ti - self._half:ti + self._half + 1,
                            tj - self._half:tj + self._half + 1])

        # add to overall
        samples.append(sample)

      return np.array(samples)
    else:
      # retrieve coordinates for given index
      i, j = self._inds[val]

      # add first image patch
      samples = [self._imgs[0][i:i + self._patch_size, j:j + self._patch_size]]

      # add remaining image patches
      for k, img in enumerate(self._imgs[1:]):
        # find transformed coordinates of patch
        ti, tj = self._transfs[k]((i + self._half, j + self._half))

        # convert them to int
        ti = int(np.round(ti))
        tj = int(np.round(tj))

        # add to overall
        samples.append(img[ti - self._half:ti + self._half + 1,
                           tj - self._half:tj + self._half + 1])

      return samples

  def __len__(self):
    return len(self._inds)