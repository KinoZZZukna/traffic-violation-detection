import { Component } from '@angular/core';

import { VideoStreamComponent } from './video-stream/video-stream.component';

@Component({
  selector: 'app-root',
  imports: [VideoStreamComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  title = 'video-detection-frontend';
}
