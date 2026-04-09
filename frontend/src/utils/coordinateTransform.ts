import type { SiteBoundary } from "../types/layout";

export interface CoordinateTransform {
  canvasHeight: number;
  canvasWidth: number;
  offsetX: number;
  offsetY: number;
  realHeight: number;
  realWidth: number;
  scale: number;
  toScreenX: (realX: number) => number;
  toScreenY: (realY: number) => number;
  toScreenPoint: (realX: number, realY: number) => { x: number; y: number };
  toScreenRect: (
    centerX: number,
    centerY: number,
    realWidth: number,
    realHeight: number,
  ) => { height: number; left: number; top: number; width: number };
}

export const createCoordinateTransform = (
  boundary: SiteBoundary,
  canvasWidth: number,
  canvasHeight: number,
): CoordinateTransform => {
  const realWidth = Math.max(boundary.max_x - boundary.min_x, 1);
  const realHeight = Math.max(boundary.max_y - boundary.min_y, 1);
  const scale = Math.min(canvasWidth / realWidth, canvasHeight / realHeight) * 0.9;

  const scaledWidth = realWidth * scale;
  const scaledHeight = realHeight * scale;
  const offsetX = (canvasWidth - scaledWidth) / 2;
  const offsetY = (canvasHeight - scaledHeight) / 2;

  const toScreenX = (realX: number) => offsetX + (realX - boundary.min_x) * scale;

  // Canvas Y grows downward, so we invert the mathematical Y axis here.
  const toScreenY = (realY: number) => canvasHeight - offsetY - (realY - boundary.min_y) * scale;

  const toScreenPoint = (realX: number, realY: number) => ({
    x: toScreenX(realX),
    y: toScreenY(realY),
  });

  const toScreenRect = (
    centerX: number,
    centerY: number,
    rectWorldWidth: number,
    rectWorldHeight: number,
  ) => {
    const width = rectWorldWidth * scale;
    const height = rectWorldHeight * scale;
    const left = toScreenX(centerX - rectWorldWidth / 2);
    const top = toScreenY(centerY + rectWorldHeight / 2);

    return { left, top, width, height };
  };

  return {
    canvasHeight,
    canvasWidth,
    offsetX,
    offsetY,
    realHeight,
    realWidth,
    scale,
    toScreenX,
    toScreenY,
    toScreenPoint,
    toScreenRect,
  };
};
