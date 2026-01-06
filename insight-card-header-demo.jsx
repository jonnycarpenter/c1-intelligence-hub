import React, { useState } from 'react';

const InsightCardDemo = () => {
  const [selectedStyle, setSelectedStyle] = useState('warm');

  const headerStyles = {
    warm: {
      background: 'rgba(251, 191, 36, 0.08)',
      padding: '10px 14px',
      borderRadius: '6px',
      marginBottom: '12px',
    },
    accent: {
      background: 'rgba(100, 116, 139, 0.06)',
      borderLeft: '3px solid #f59e0b',
      padding: '10px 14px',
      borderRadius: '0 6px 6px 0',
      marginBottom: '12px',
    },
    gradient: {
      background: 'linear-gradient(90deg, rgba(251, 191, 36, 0.10) 0%, transparent 70%)',
      padding: '10px 14px',
      borderRadius: '6px',
      marginBottom: '12px',
    },
    none: {
      padding: '10px 14px',
      marginBottom: '12px',
    }
  };

  const insightCards = [
    {
      title: 'SPACE LAUNCH COMPOSITES INFLECTION',
      badge: 'NET NEW',
      badgeColor: '#22c55e',
      companies: ['🚀', '🛰️', '🔧', '⚙️'],
      headline: 'Rocket Lab wins record $816M prime contract for missile defense satellite constellation, surpassing previous $515M defense award and validating composite-intensive small launch vehicle economics',
      timestamp: '11 25 46',
      source: '[Exa:6]',
      bullets: [
        'Rocket Lab completed 21 launches in 2025 with 100% mission success rate, positioning Neutron medium-lift vehicle deb...'
      ]
    },
    {
      title: 'AEROSPACE OEM RECOVERY VALIDATION',
      badge: 'CONTINUING',
      badgeColor: '#6b7280',
      companies: ['✈️', '🔩', '🏭', '📊'],
      headline: 'Airbus confirms 793 aircraft deliveries in 2025 exceeding revised target, with audited data due January 12—validates composite-intensive narrowbody production rate sustainability',
      timestamp: '20 35',
      bullets: [
        'GE Aerospace stock +84% in 2025 driven by flight departure growth and easing supply chain crisis, signaling engine co...'
      ]
    },
    {
      title: 'SUPPLY CHAIN REALIGNMENT SIGNAL',
      badge: 'EMERGING',
      badgeColor: '#3b82f6',
      companies: ['🏗️', '📦', '🚚', '🔄'],
      headline: 'Major tier-1 suppliers announce capacity expansion in North American facilities, indicating reshoring momentum for composite material processing',
      timestamp: '18 42',
      bullets: [
        'Hexcel expands Utah carbon fiber production line, adding 15% capacity for aerospace prepreg materials...'
      ]
    }
  ];

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f8fafc', 
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Style Selector */}
      <div style={{ 
        marginBottom: '24px', 
        padding: '16px', 
        backgroundColor: 'white', 
        borderRadius: '8px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#64748b', fontWeight: '600' }}>
          HEADER STYLE OPTIONS
        </h3>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { key: 'none', label: 'No Background (Current)' },
            { key: 'warm', label: 'Option 1: Warm Tint' },
            { key: 'accent', label: 'Option 2: Left Accent' },
            { key: 'gradient', label: 'Option 3: Gradient Fade' },
          ].map(option => (
            <button
              key={option.key}
              onClick={() => setSelectedStyle(option.key)}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: selectedStyle === option.key ? '2px solid #f59e0b' : '2px solid #e2e8f0',
                backgroundColor: selectedStyle === option.key ? 'rgba(251, 191, 36, 0.1)' : 'white',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: selectedStyle === option.key ? '600' : '400',
                color: '#334155',
                transition: 'all 0.15s ease'
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Need to Know Section */}
      <div style={{ 
        backgroundColor: 'white', 
        borderRadius: '12px', 
        padding: '20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px', 
          marginBottom: '20px',
          paddingBottom: '12px',
          borderBottom: '1px solid #e2e8f0'
        }}>
          <span style={{ fontSize: '18px' }}>🎯</span>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: '700', color: '#1e293b' }}>
            NEED TO KNOW
          </h2>
          <span style={{ 
            fontSize: '12px', 
            color: '#64748b',
            backgroundColor: '#f1f5f9',
            padding: '2px 8px',
            borderRadius: '4px'
          }}>
            3 insights
          </span>
        </div>

        {/* Insight Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {insightCards.map((card, index) => (
            <div 
              key={index}
              style={{ 
                borderBottom: index < insightCards.length - 1 ? '1px solid #f1f5f9' : 'none',
                paddingBottom: index < insightCards.length - 1 ? '20px' : '0'
              }}
            >
              {/* Header with dynamic styling */}
              <div style={headerStyles[selectedStyle]}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h3 style={{ 
                    margin: 0, 
                    fontSize: '13px', 
                    fontWeight: '700', 
                    color: '#1e293b',
                    letterSpacing: '0.025em'
                  }}>
                    {card.title}
                  </h3>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {card.companies.map((emoji, i) => (
                      <span key={i} style={{ 
                        fontSize: '14px',
                        backgroundColor: '#f8fafc',
                        borderRadius: '4px',
                        padding: '2px 4px'
                      }}>
                        {emoji}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Content */}
              <div style={{ paddingLeft: selectedStyle === 'accent' ? '17px' : '0' }}>
                <p style={{ 
                  margin: '0 0 8px 0', 
                  fontSize: '15px', 
                  color: '#334155',
                  lineHeight: '1.5'
                }}>
                  <strong>{card.headline.split(' ').slice(0, 2).join(' ')}</strong>
                  {' '}{card.headline.split(' ').slice(2).join(' ')}
                  <span style={{ color: '#94a3b8', fontSize: '12px', marginLeft: '6px' }}>
                    {card.timestamp}
                  </span>
                  <span style={{ color: '#3b82f6', fontSize: '12px', marginLeft: '4px' }}>
                    {card.source}
                  </span>
                </p>

                <span style={{
                  display: 'inline-block',
                  fontSize: '11px',
                  fontWeight: '600',
                  color: card.badgeColor,
                  backgroundColor: `${card.badgeColor}15`,
                  padding: '3px 8px',
                  borderRadius: '4px',
                  marginBottom: '10px'
                }}>
                  ✦ {card.badge}
                </span>

                {card.bullets.map((bullet, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginTop: '8px' }}>
                    <span style={{ color: '#f59e0b', marginTop: '6px', fontSize: '8px' }}>●</span>
                    <p style={{ margin: 0, fontSize: '14px', color: '#64748b', lineHeight: '1.5' }}>
                      {bullet}
                    </p>
                  </div>
                ))}

                <button style={{
                  background: 'none',
                  border: 'none',
                  color: '#f59e0b',
                  fontSize: '13px',
                  cursor: 'pointer',
                  padding: '4px 0',
                  marginTop: '4px'
                }}>
                  ∨ Show 3 more insights
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CSS Code Preview */}
      <div style={{ 
        marginTop: '24px', 
        padding: '16px', 
        backgroundColor: '#1e293b', 
        borderRadius: '8px',
        color: '#e2e8f0',
        fontSize: '13px',
        fontFamily: 'Monaco, Consolas, monospace'
      }}>
        <div style={{ color: '#94a3b8', marginBottom: '8px' }}>// Current selection CSS:</div>
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
          {selectedStyle === 'none' && `/* No background styling */
padding: 10px 14px;`}
          {selectedStyle === 'warm' && `/* Warm tint - matches brand amber */
background: rgba(251, 191, 36, 0.08);
padding: 10px 14px;
border-radius: 6px;`}
          {selectedStyle === 'accent' && `/* Left accent bar - structured feel */
background: rgba(100, 116, 139, 0.06);
border-left: 3px solid #f59e0b;
padding: 10px 14px;
border-radius: 0 6px 6px 0;`}
          {selectedStyle === 'gradient' && `/* Gradient fade - subtle & sophisticated */
background: linear-gradient(90deg, 
  rgba(251, 191, 36, 0.10) 0%, 
  transparent 70%);
padding: 10px 14px;
border-radius: 6px;`}
        </pre>
      </div>
    </div>
  );
};

export default InsightCardDemo;
