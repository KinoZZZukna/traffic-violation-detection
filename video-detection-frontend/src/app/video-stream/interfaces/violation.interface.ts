/**
 * Интерфейс для записи нарушения.
 */
export interface Violation {
  id: number;
  vehicle_id: string;
  timestamp: string;
  video_second: number;
  processed_video_path: string;
  original_video_path: string;
}
