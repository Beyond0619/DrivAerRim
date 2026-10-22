import torch 
from dataclasses import dataclass
from typing import Union, Tuple

def rescale_new(x: torch.Tensor, lims=(-1,1), phys_domain = ([-1, -1, -1], [1, 1, 1])):
    # Scale coordinates into a uniform [-1,1]^d box while preserving aspect ratio.
    # Uc'dse the maximum length scale among all physical dimensions, not per-axis min/max.
    phys_domain_tensor = torch.as_tensor(phys_domain, dtype=x.dtype, device=x.device)
    min_vals = phys_domain_tensor[0]
    max_vals = phys_domain_tensor[1]
    centers = (min_vals + max_vals) / 2.0
    half_ranges = (max_vals - min_vals) / 2.0
    max_half_range = half_ranges.max()
    if max_half_range == 0:
        return x.clone().to(x.dtype)

    rescaled = (x - centers) / max_half_range
    lower, upper = lims
    if lower != -1 or upper != 1:
        rescaled = rescaled * ((upper - lower) / 2.0) + (upper + lower) / 2.0
    return rescaled

def rescale(x:torch.Tensor, lims=(-1,1))->torch.Tensor:
    """
    Parameters
    ----------
    x: torch.Tensor
        ND tensor
    
    Returns
    -------
    x_normalized: torch.Tensor
        ND tensor
    """
    return (x-x.min()) / (x.max()-x.min()) * (lims[1] - lims[0]) + lims[0]


@dataclass
class MeanStd:
    mean:torch.Tensor
    std:torch.Tensor

def normalize(x:torch.Tensor, mean=None, std=None, return_mean_std:bool=False
              )->Union[torch.Tensor, Tuple[torch.Tensor, MeanStd]]:
    """
    Parameters
    ----------
    x: torch.Tensor
        ND tensor
    mean: Optional[float]
        mean of the data
    std: Optional[float]
        standard deviation of the data
    
    Returns
    -------
    x_normalized: torch.Tensor
        1D tensor
    """
    if mean is None:
        mean = x.mean()
    if std is None:
        std = x.std()
    if return_mean_std:
        return (x - mean) / std, MeanStd(mean, std)
    else:
        return (x - mean) / std
