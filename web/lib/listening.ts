export type VoiceCommand = 'pause' | 'resume' | 'next' | 'repeat' | 'evidence' | null;
export function voiceCommand(raw: string): VoiceCommand {
  const text = raw.toLowerCase().replace(/[.,!?]/g, '').replace(/^(hey\s+)?kumail[, ]+/, '').trim();
  if (/^(pause|stop)( (the )?(briefing|audio|playback))?$/.test(text)) return 'pause';
  if (/^(resume|continue|carry on)( (the |my )?(briefing|audio|playback))?$/.test(text)) return 'resume';
  if (/^(next|skip|next story|skip (this |the )?(story|one))$/.test(text)) return 'next';
  if (/^(repeat|repeat (that|this|this story|the story)|start (this |the )?story again)$/.test(text)) return 'repeat';
  if (/^(show (the )?(sources|evidence)|where is this from|read this)$/.test(text)) return 'evidence';
  return null;
}
export function clock(seconds: number) {
  const value = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}
export function mentionedStory(text: string): number | null {
  const words=['first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth'];
  const lower=text.toLowerCase();
  const ordinal=lower.match(/\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:story|headline)\b/);
  if(ordinal)return words.indexOf(ordinal[1]);
  const numbered=lower.match(/\b(?:story|headline)\s+(\d{1,2})\b/);
  return numbered&&Number(numbered[1])>0?Number(numbered[1])-1:null;
}
