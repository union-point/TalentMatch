import { Check, Minus } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export function StatusBadge({ pass }: { pass: boolean }) {
  return <Badge variant={pass ? 'default' : 'outline'}>
    {pass ? <Check /> : <Minus />}{pass ? 'Pass' : 'Fail'}
  </Badge>;
}
