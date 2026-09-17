"""FloodUNet PyTorch model architecture for Sentinel-2 6-band flood segmentation.

Matches exact checkpoint topology in best_model.pth (7,763,905 parameters).
Trained on Sen1Floods11 v1.1 using bands: [B2, B3, B4, B8, B11, B12].
"""

import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    """Double 3x3 Conv block with BatchNorm and ReLU (bias=False for convolutions before BatchNorm)."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class Down(nn.Module):
    """Downscaling block: 2x2 MaxPool followed by DoubleConv."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(x)
        return self.conv(x)


class Up(nn.Module):
    """Upscaling block: 2x2 ConvTranspose2d followed by channel concatenation and DoubleConv."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, out_channels, kernel_size=2, stride=2, bias=True)
        self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        x1 = self.up(x1)
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class FloodUNet(nn.Module):
    """
    6-band U-Net segmentation network.
    Input shape: (batch_size, 6, H, W) where channels correspond to [B2, B3, B4, B8, B11, B12].
    Output shape: (batch_size, 1, H, W) raw logits.
    """

    def __init__(self, in_channels: int = 6, base_channels: int = 32, out_channels: int = 1):
        super().__init__()
        self.enc1 = DoubleConv(in_channels, base_channels)
        self.enc2 = Down(base_channels, base_channels * 2)
        self.enc3 = Down(base_channels * 2, base_channels * 4)
        self.enc4 = Down(base_channels * 4, base_channels * 8)
        self.bottleneck = Down(base_channels * 8, base_channels * 16)

        self.up4 = Up(base_channels * 16, base_channels * 8)
        self.up3 = Up(base_channels * 8, base_channels * 4)
        self.up2 = Up(base_channels * 4, base_channels * 2)
        self.up1 = Up(base_channels * 2, base_channels)

        self.out = nn.Conv2d(base_channels, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.enc1(x)
        x2 = self.enc2(x1)
        x3 = self.enc3(x2)
        x4 = self.enc4(x3)
        b = self.bottleneck(x4)

        x = self.up4(b, x4)
        x = self.up3(x, x3)
        x = self.up2(x, x2)
        x = self.up1(x, x1)
        return self.out(x)
