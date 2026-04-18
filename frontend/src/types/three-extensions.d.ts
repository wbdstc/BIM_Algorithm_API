declare module "three/examples/jsm/controls/OrbitControls.js" {
  import { Camera, EventDispatcher, Vector3 } from "three";

  export class OrbitControls extends EventDispatcher {
    constructor(object: Camera, domElement?: HTMLElement);

    object: Camera;
    domElement: HTMLElement;
    enabled: boolean;
    target: Vector3;
    minDistance: number;
    maxDistance: number;
    minPolarAngle: number;
    maxPolarAngle: number;
    minAzimuthAngle: number;
    maxAzimuthAngle: number;
    enablePan: boolean;
    enableDamping: boolean;
    dampingFactor: number;

    update(): void;
    dispose(): void;
  }
}
