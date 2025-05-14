/**
 * Интерфейс для данных детекции на кадре.
 */
export interface DetectionData {
  vehicles?: any[];
  traffic_lights?: any[];
  crosswalk_bbox?: number[];
  total_crossings?: number;
  red_light_violations?: number;
  frame_width?: number;
  frame_height?: number;
  vehicle_states?: { [id: string]: { crossed: boolean; crossed_on_red: boolean } };
  output_path?: string;
}
