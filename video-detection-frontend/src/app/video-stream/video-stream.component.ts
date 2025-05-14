import { CommonModule } from '@angular/common';
import { Component, ElementRef, ViewChild, OnInit, OnDestroy } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatTableModule } from '@angular/material/table';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';

import {DetectionData} from './interfaces/detection-data.interface';
import {Violation} from './interfaces/violation.interface';

@Component({
  selector: 'app-video-stream',
  templateUrl: './video-stream.component.html',
  styleUrls: ['./video-stream.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule, MatInputModule, MatTableModule, MatCardModule, MatToolbarModule,
    MatIconModule, MatListModule, MatExpansionModule, MatTooltipModule
  ]
})
export class VideoStreamComponent implements OnInit, OnDestroy {
  @ViewChild('overlayCanvas', { static: false }) overlayCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('videoImage', { static: false }) videoImage!: ElementRef<HTMLImageElement>;

  detectionData: DetectionData | null = null;
  filePath = '';
  processedVideoFilename: string | null = null;
  processing = false;
  uploading = false;
  violations: Violation[] = [];

  private ws: WebSocket | null = null;

  /**
   * Хук жизненного цикла Angular. Вызывается один раз после инициализации компонента.
   * Используется для начальной загрузки истории нарушений.
   */
  ngOnInit() {
    this.loadViolations();
  }

  /**
   * Хук жизненного цикла Angular. Вызывается непосредственно перед уничтожением компонента.
   * Используется для остановки обработки видео и закрытия WebSocket соединения.
   */
  ngOnDestroy() {
    this.stopProcessing();
  }

  /**
   * Асинхронно загружает историю нарушений с сервера.
   * Отправляет GET-запрос на эндпоинт '/violations'.
   */
  async loadViolations() {
    try {
      const response = await fetch('http://localhost:8000/violations');
      if (!response.ok) {
        throw new Error(`Ошибка HTTP: ${response.status}`);
      }
      this.violations = await response.json();
    } catch (error) {
      console.error("Не удалось загрузить историю нарушений:", error);
      // Здесь можно добавить обработку ошибки для пользователя, например, уведомление
    }
  }

  /**
   * Обрабатывает событие выбора файла пользователем.
   * Вызывается при изменении значения элемента input type="file".
   * @param event Событие выбора файла.
   */
  async onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.uploading = true;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('http://localhost:8000/process_video_file', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        throw new Error(`Ошибка HTTP: ${response.status}`);
      }
      const data = await response.json();
      this.filePath = data.file_path;
    } catch (error) {
      console.error("Ошибка при загрузке файла:", error);
    } finally {
      this.uploading = false;
    }
  }

  downloadProcessedVideo() {
    if (!this.processedVideoFilename) return;
    window.open(`http://localhost:8000/download_processed_video?filename=${this.processedVideoFilename}`, '_blank');
  }

  getOriginalVideoUrl(v: Violation): string {
    if (!v.original_video_path) return '';
    const filename = v.original_video_path.split(/[\\/]/).pop();
    return `http://localhost:8000/uploaded_videos/${filename}`;
  }

  getProcessedVideoUrl(v: Violation): string {
    if (!v.processed_video_path) return '';
    const filename = v.processed_video_path.split(/[\\/]/).pop();
    return `http://localhost:8000/download_processed_video?filename=${filename}`;
  }

  getRedLightViolators(): (string | number)[] {
    if (!this.detectionData?.vehicle_states) return [];
    return Object.entries(this.detectionData.vehicle_states)
      .filter(([_, state]) => state.crossed_on_red)
      .map(([id]) => id);
  }

  startProcessing() {
    if (!this.filePath) return;
    this.prepareForProcessing();
    this.openWebSocket(this.filePath);
  }

  startWebcam() {
    this.prepareForProcessing();
    this.openWebSocket('0');
  }

  stopProcessing() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.processing = false;
  }

  private handleWebSocketMessage(event: MessageEvent) {
    if (typeof event.data === 'string') {
      const msg = JSON.parse(event.data);
      if (msg.type === 'frame_data') {
        this.detectionData = msg.data;
        if (msg.data.output_path) {
          this.processedVideoFilename = msg.data.output_path.split(/[\\/]/).pop();
        }
      }
    } else if (event.data instanceof ArrayBuffer) {
      const blob = new Blob([event.data], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);
      const img = this.videoImage?.nativeElement;
      if (img) {
        img.onload = () => URL.revokeObjectURL(url);
        img.src = url;
      }
    }
  }

  private openWebSocket(source: string) {
    this.stopProcessing();
    this.processing = true;
    this.ws = new WebSocket('ws://localhost:8000/ws/video_feed');
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify({ file_path: source }));
    };
    this.ws.onmessage = (event) => this.handleWebSocketMessage(event);
    this.ws.onclose = () => {
      this.processing = false;
    };
    this.ws.onerror = (error) => {
        console.error("Ошибка WebSocket:", error);
        this.processing = false;
    };
  }

  private prepareForProcessing() {
    this.processedVideoFilename = null;
    this.detectionData = null;
  }

  private drawBoundingBoxes() {
    if (!this.detectionData || !this.overlayCanvas?.nativeElement || !this.videoImage?.nativeElement) return;
    const canvas = this.overlayCanvas.nativeElement;
    const img = this.videoImage.nativeElement;
    const frameWidth = this.detectionData.frame_width || img.naturalWidth;
    const frameHeight = this.detectionData.frame_height || img.naturalHeight;
    canvas.width = img.width;
    canvas.height = img.height;
    const scaleX = img.width / frameWidth;
    const scaleY = img.height / frameHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (this.detectionData.vehicles) {
      ctx.strokeStyle = 'yellow';
      ctx.lineWidth = 2;
      ctx.font = '14px Arial';
      ctx.fillStyle = 'yellow';
      for (const veh of this.detectionData.vehicles) {
        const [x1, y1, x2, y2] = veh.bbox;
        const sx = x1 * scaleX;
        const sy = y1 * scaleY;
        const sw = (x2 - x1) * scaleX;
        const sh = (y2 - y1) * scaleY;
        ctx.strokeRect(sx, sy, sw, sh);
        ctx.fillText(`${veh.label} (${veh.id})`, sx + 2, sy + 16);
      }
    }
    if (this.detectionData.traffic_lights) {
      for (const light of this.detectionData.traffic_lights) {
        const [x1, y1, x2, y2] = light.bbox;
        ctx.strokeStyle = light.label === 'red_light' ? 'red' : (light.label === 'green_light' ? 'green' : 'orange');
        ctx.lineWidth = 2;
        const sx = x1 * scaleX;
        const sy = y1 * scaleY;
        const sw = (x2 - x1) * scaleX;
        const sh = (y2 - y1) * scaleY;
        ctx.strokeRect(sx, sy, sw, sh);
        ctx.fillStyle = ctx.strokeStyle as string;
        ctx.fillText(light.label, sx + 2, sy + 16);
      }
    }
    if (this.detectionData.crosswalk_bbox) {
      const [x, y, w, h] = this.detectionData.crosswalk_bbox;
      ctx.strokeStyle = 'blue';
      ctx.lineWidth = 2;
      ctx.strokeRect(x * scaleX, y * scaleY, w * scaleX, h * scaleY);
      ctx.fillStyle = 'blue';
      ctx.fillText('Crosswalk', x * scaleX + 2, y * scaleY + 16);
    }
  }
}
