/**
 * Obsidian Lexicon Design System Tokens
 * Unified theme structure used across all LegalOS enterprise workspace modules.
 */
export const tokens = {
  colors: {
    canvas: {
      base: '#090D16',       // Deep Canvas Void
      subtle: '#0D1322',     // Workspace canvas, panels
      elevated: '#141C30',   // Cards, drawers, modal sheets
      glass: 'rgba(20, 28, 48, 0.72)',
    },
    border: {
      hairline: 'rgba(255, 255, 255, 0.08)',
      subtle: 'rgba(255, 255, 255, 0.14)',
      active: 'rgba(59, 130, 246, 0.50)',
    },
    brand: {
      primary: '#3B82F6',    // Sapphire Intelligence
      hover: '#2563EB',
      light: '#60A5FA',
      glow: 'rgba(59, 130, 246, 0.25)',
    },
    risk: {
      low: '#10B981',        // Emerald Compliance
      lowBg: 'rgba(16, 185, 129, 0.12)',
      lowText: '#34D399',
      lowBorder: 'rgba(16, 185, 129, 0.3)',
      medium: '#F59E0B',     // Amber Deadline Looming
      mediumBg: 'rgba(245, 158, 11, 0.12)',
      mediumText: '#FBBF24',
      mediumBorder: 'rgba(245, 158, 11, 0.3)',
      high: '#EF4444',       // Ruby Critical Exposure
      highBg: 'rgba(239, 68, 68, 0.12)',
      highText: '#F87171',
      highBorder: 'rgba(239, 68, 68, 0.4)',
      none: '#64748B',
      noneBg: 'rgba(100, 116, 139, 0.12)',
      noneText: '#94A3B8',
      noneBorder: 'rgba(100, 116, 139, 0.2)'
    },
    text: {
      primary: '#F8FAFC',
      secondary: '#94A3B8',
      muted: '#64748B'
    }
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '20px',
    xl: '32px'
  },
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    full: '9999px'
  },
  typography: {
    fontSans: 'Inter, system-ui, -apple-system, sans-serif',
    fontMono: 'JetBrains Mono, monospace'
  }
};

