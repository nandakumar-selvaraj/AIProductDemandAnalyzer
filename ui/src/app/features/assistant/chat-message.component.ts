import { DatePipe } from '@angular/common';
import { Component, computed, input, signal } from '@angular/core';
import { ChatMessage } from '../../core/models/assistant.models';

interface Part {
  text: string;
  bold: boolean;
}
export function messageLines(text: string) {
  return text.split('\n').map((line) => ({
    bullet: /^\s*[-*]\s+/.test(line),
    parts: line
      .replace(/^\s*[-*]\s+/, '')
      .split(/(\*\*[^*\n]+\*\*)/g)
      .filter(Boolean)
      .map((part): Part => ({
        bold: part.startsWith('**') && part.endsWith('**'),
        text: part.startsWith('**') && part.endsWith('**') ? part.slice(2, -2) : part,
      })),
  }));
}

@Component({
  selector: 'app-assistant-message',
  imports: [DatePipe],
  templateUrl: './chat-message.component.html',
  styleUrl: './chat-message.component.scss',
})
export class ChatMessageComponent {
  readonly message = input.required<ChatMessage>();
  protected readonly lines = computed(() => messageLines(this.message().text));
  protected readonly copyStatus = signal('');
  protected async copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.message().text);
      this.copyStatus.set('Response copied.');
    } catch {
      this.copyStatus.set('Copy unavailable. Select the response text to copy it.');
    }
  }
}
