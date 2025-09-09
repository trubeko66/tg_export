#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для генерации HTML отчетов с интерактивными графиками
"""

import json
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict

from analytics import AnalyticsEngine, ChannelAnalytics, ExportAnalytics


class HTMLReporter:
    """Генератор HTML отчетов"""
    
    def __init__(self):
        self.analytics_engine = AnalyticsEngine(None)  # Без консоли для HTML
    
    def generate_html_report(self, channels_data: List[Tuple[Path, str]], output_file: Path):
        """Генерация HTML отчета"""
        try:
            # Анализируем данные
            analytics_data = []
            for channel_dir, channel_name in channels_data:
                analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
                analytics_data.append(analytics)
            
            # Генерируем HTML
            html_content = self._create_html_template(analytics_data)
            
            # Сохраняем файл
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"HTML отчет создан: {output_file}")
            
        except Exception as e:
            print(f"Ошибка создания HTML отчета: {e}")
    
    def _create_html_template(self, analytics_data: List[ChannelAnalytics]) -> str:
        """Создание HTML шаблона"""
        
        # Подготавливаем данные для графиков
        chart_data = self._prepare_chart_data(analytics_data)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Аналитика Telegram каналов</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 2em;
            font-weight: bold;
        }}
        
        .stat-card p {{
            margin: 0;
            opacity: 0.9;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .chart-title {{
            font-size: 1.5em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #333;
            text-align: center;
        }}
        
        .table-container {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #eee;
        }}
        
        .loading {{
            text-align: center;
            padding: 50px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Аналитика Telegram каналов</h1>
            <p>Отчет сгенерирован {datetime.now().strftime('%d.%m.%Y в %H:%M')}</p>
        </div>
        
        <div class="content">
            <!-- Общая статистика -->
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{len(analytics_data)}</h3>
                    <p>Всего каналов</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_messages for a in analytics_data):,}</h3>
                    <p>Всего сообщений</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_media_files for a in analytics_data):,}</h3>
                    <p>Медиафайлов</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_size_mb for a in analytics_data):.1f} МБ</h3>
                    <p>Общий размер</p>
                </div>
            </div>
            
            <!-- График активности каналов -->
            <div class="chart-container">
                <div class="chart-title">📈 Активность каналов</div>
                <div id="activityChart" style="height: 400px;"></div>
            </div>
            
            <!-- График размеров медиа -->
            <div class="chart-container">
                <div class="chart-title">💾 Размеры медиафайлов</div>
                <div id="mediaChart" style="height: 400px;"></div>
            </div>
            
            <!-- График вовлеченности -->
            <div class="chart-container">
                <div class="chart-title">🎯 Уровень вовлеченности</div>
                <div id="engagementChart" style="height: 400px;"></div>
            </div>
            
            <!-- Детальная таблица -->
            <div class="table-container">
                <div class="chart-title">📋 Детальная статистика</div>
                <table>
                    <thead>
                        <tr>
                            <th>Канал</th>
                            <th>Сообщений</th>
                            <th>Медиа</th>
                            <th>Размер (МБ)</th>
                            <th>Активность/день</th>
                            <th>Вовлеченность</th>
                            <th>Рост (%)</th>
                            <th>Последняя активность</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_table_rows(analytics_data)}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Сгенерировано Telegram Channel Exporter v1.2.0</p>
        </div>
    </div>
    
    <script>
        // График активности каналов
        var activityData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['message_counts']},
            type: 'bar',
            marker: {{
                color: 'rgba(102, 126, 234, 0.8)',
                line: {{
                    color: 'rgba(102, 126, 234, 1.0)',
                    width: 1
                }}
            }}
        }};
        
        var activityLayout = {{
            title: 'Количество сообщений по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Количество сообщений' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('activityChart', [activityData], activityLayout);
        
        // График размеров медиа
        var mediaData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['media_sizes']},
            type: 'bar',
            marker: {{
                color: 'rgba(240, 147, 251, 0.8)',
                line: {{
                    color: 'rgba(240, 147, 251, 1.0)',
                    width: 1
                }}
            }}
        }};
        
        var mediaLayout = {{
            title: 'Размер медиафайлов по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Размер (МБ)' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('mediaChart', [mediaData], mediaLayout);
        
        // График вовлеченности
        var engagementData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['engagement_rates']},
            type: 'scatter',
            mode: 'markers+lines',
            marker: {{
                size: 12,
                color: 'rgba(245, 87, 108, 0.8)',
                line: {{
                    color: 'rgba(245, 87, 108, 1.0)',
                    width: 2
                }}
            }},
            line: {{
                color: 'rgba(245, 87, 108, 0.6)',
                width: 3
            }}
        }};
        
        var engagementLayout = {{
            title: 'Уровень вовлеченности по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Уровень вовлеченности' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('engagementChart', [engagementData], engagementLayout);
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _prepare_chart_data(self, analytics_data: List[ChannelAnalytics]) -> Dict[str, List]:
        """Подготовка данных для графиков"""
        channel_names = [a.channel_name for a in analytics_data]
        message_counts = [a.total_messages for a in analytics_data]
        media_sizes = [a.total_size_mb for a in analytics_data]
        engagement_rates = [a.engagement_rate for a in analytics_data]
        
        return {
            'channel_names': json.dumps(channel_names, ensure_ascii=False),
            'message_counts': json.dumps(message_counts),
            'media_sizes': json.dumps(media_sizes),
            'engagement_rates': json.dumps(engagement_rates)
        }
    
    def _generate_table_rows(self, analytics_data: List[ChannelAnalytics]) -> str:
        """Генерация строк таблицы"""
        rows = []
        for analytics in analytics_data:
            last_activity = analytics.last_activity.strftime('%d.%m.%Y %H:%M') if analytics.last_activity else 'Неизвестно'
            
            row = f"""
                <tr>
                    <td><strong>{analytics.channel_name}</strong></td>
                    <td>{analytics.total_messages:,}</td>
                    <td>{analytics.total_media_files:,}</td>
                    <td>{analytics.total_size_mb:.1f}</td>
                    <td>{analytics.avg_messages_per_day:.1f}</td>
                    <td>{analytics.engagement_rate:.1f}</td>
                    <td>{analytics.growth_rate:.1f}</td>
                    <td>{last_activity}</td>
                </tr>
            """
            rows.append(row)
        
        return ''.join(rows)
    
    def generate_detailed_html_report(self, channels_data: List[Tuple[Path, str]], output_file: Path):
        """Генерация детального HTML отчета с дополнительными графиками"""
        try:
            # Анализируем данные
            analytics_data = []
            for channel_dir, channel_name in channels_data:
                analytics = self.analytics_engine.analyze_channel(channel_dir, channel_name)
                analytics_data.append(analytics)
            
            # Генерируем детальный HTML
            html_content = self._create_detailed_html_template(analytics_data)
            
            # Сохраняем файл
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"Детальный HTML отчет создан: {output_file}")
            
        except Exception as e:
            print(f"Ошибка создания детального HTML отчета: {e}")
    
    def _create_detailed_html_template(self, analytics_data: List[ChannelAnalytics]) -> str:
        """Создание детального HTML шаблона"""
        
        # Подготавливаем расширенные данные для графиков
        chart_data = self._prepare_detailed_chart_data(analytics_data)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Детальная аналитика Telegram каналов</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 1.8em;
            font-weight: bold;
        }}
        
        .stat-card p {{
            margin: 0;
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            margin-bottom: 30px;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .chart-title {{
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #333;
            text-align: center;
        }}
        
        .table-container {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
            font-size: 0.9em;
        }}
        
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Детальная аналитика Telegram каналов</h1>
            <p>Расширенный отчет сгенерирован {datetime.now().strftime('%d.%m.%Y в %H:%M')}</p>
        </div>
        
        <div class="content">
            <!-- Общая статистика -->
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{len(analytics_data)}</h3>
                    <p>Всего каналов</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_messages for a in analytics_data):,}</h3>
                    <p>Всего сообщений</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_media_files for a in analytics_data):,}</h3>
                    <p>Медиафайлов</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.total_size_mb for a in analytics_data):.1f} МБ</h3>
                    <p>Общий размер</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.avg_messages_per_day for a in analytics_data):.1f}</h3>
                    <p>Средняя активность/день</p>
                </div>
                <div class="stat-card">
                    <h3>{sum(a.engagement_rate for a in analytics_data) / len(analytics_data) if analytics_data else 0:.1f}</h3>
                    <p>Средняя вовлеченность</p>
                </div>
            </div>
            
            <!-- Сетка графиков -->
            <div class="charts-grid">
                <!-- График активности каналов -->
                <div class="chart-container">
                    <div class="chart-title">📈 Активность каналов</div>
                    <div id="activityChart" style="height: 300px;"></div>
                </div>
                
                <!-- График размеров медиа -->
                <div class="chart-container">
                    <div class="chart-title">💾 Размеры медиафайлов</div>
                    <div id="mediaChart" style="height: 300px;"></div>
                </div>
                
                <!-- График вовлеченности -->
                <div class="chart-container">
                    <div class="chart-title">🎯 Уровень вовлеченности</div>
                    <div id="engagementChart" style="height: 300px;"></div>
                </div>
                
                <!-- График роста -->
                <div class="chart-container">
                    <div class="chart-title">📊 Темп роста</div>
                    <div id="growthChart" style="height: 300px;"></div>
                </div>
            </div>
            
            <!-- Детальная таблица -->
            <div class="table-container">
                <div class="chart-title">📋 Детальная статистика</div>
                <table>
                    <thead>
                        <tr>
                            <th>Канал</th>
                            <th>Сообщений</th>
                            <th>Медиа</th>
                            <th>Размер (МБ)</th>
                            <th>Активность/день</th>
                            <th>Вовлеченность</th>
                            <th>Рост (%)</th>
                            <th>Пиковые часы</th>
                            <th>Последняя активность</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_detailed_table_rows(analytics_data)}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Сгенерировано Telegram Channel Exporter v1.2.0</p>
        </div>
    </div>
    
    <script>
        // График активности каналов
        var activityData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['message_counts']},
            type: 'bar',
            marker: {{
                color: 'rgba(102, 126, 234, 0.8)',
                line: {{
                    color: 'rgba(102, 126, 234, 1.0)',
                    width: 1
                }}
            }}
        }};
        
        var activityLayout = {{
            title: 'Количество сообщений по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Количество сообщений' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('activityChart', [activityData], activityLayout);
        
        // График размеров медиа
        var mediaData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['media_sizes']},
            type: 'bar',
            marker: {{
                color: 'rgba(240, 147, 251, 0.8)',
                line: {{
                    color: 'rgba(240, 147, 251, 1.0)',
                    width: 1
                }}
            }}
        }};
        
        var mediaLayout = {{
            title: 'Размер медиафайлов по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Размер (МБ)' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('mediaChart', [mediaData], mediaLayout);
        
        // График вовлеченности
        var engagementData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['engagement_rates']},
            type: 'scatter',
            mode: 'markers+lines',
            marker: {{
                size: 12,
                color: 'rgba(245, 87, 108, 0.8)',
                line: {{
                    color: 'rgba(245, 87, 108, 1.0)',
                    width: 2
                }}
            }},
            line: {{
                color: 'rgba(245, 87, 108, 0.6)',
                width: 3
            }}
        }};
        
        var engagementLayout = {{
            title: 'Уровень вовлеченности по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Уровень вовлеченности' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('engagementChart', [engagementData], engagementLayout);
        
        // График роста
        var growthData = {{
            x: {chart_data['channel_names']},
            y: {chart_data['growth_rates']},
            type: 'bar',
            marker: {{
                color: 'rgba(76, 175, 80, 0.8)',
                line: {{
                    color: 'rgba(76, 175, 80, 1.0)',
                    width: 1
                }}
            }}
        }};
        
        var growthLayout = {{
            title: 'Темп роста по каналам',
            xaxis: {{ title: 'Каналы' }},
            yaxis: {{ title: 'Темп роста (%)' }},
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        }};
        
        Plotly.newPlot('growthChart', [growthData], growthLayout);
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _prepare_detailed_chart_data(self, analytics_data: List[ChannelAnalytics]) -> Dict[str, List]:
        """Подготовка расширенных данных для графиков"""
        channel_names = [a.channel_name for a in analytics_data]
        message_counts = [a.total_messages for a in analytics_data]
        media_sizes = [a.total_size_mb for a in analytics_data]
        engagement_rates = [a.engagement_rate for a in analytics_data]
        growth_rates = [a.growth_rate for a in analytics_data]
        
        return {
            'channel_names': json.dumps(channel_names, ensure_ascii=False),
            'message_counts': json.dumps(message_counts),
            'media_sizes': json.dumps(media_sizes),
            'engagement_rates': json.dumps(engagement_rates),
            'growth_rates': json.dumps(growth_rates)
        }
    
    def _generate_detailed_table_rows(self, analytics_data: List[ChannelAnalytics]) -> str:
        """Генерация строк детальной таблицы"""
        rows = []
        for analytics in analytics_data:
            last_activity = analytics.last_activity.strftime('%d.%m.%Y %H:%M') if analytics.last_activity else 'Неизвестно'
            peak_hours = ', '.join(map(str, analytics.peak_hours)) if analytics.peak_hours else 'Нет данных'
            
            row = f"""
                <tr>
                    <td><strong>{analytics.channel_name}</strong></td>
                    <td>{analytics.total_messages:,}</td>
                    <td>{analytics.total_media_files:,}</td>
                    <td>{analytics.total_size_mb:.1f}</td>
                    <td>{analytics.avg_messages_per_day:.1f}</td>
                    <td>{analytics.engagement_rate:.1f}</td>
                    <td>{analytics.growth_rate:.1f}</td>
                    <td>{peak_hours}</td>
                    <td>{last_activity}</td>
                </tr>
            """
            rows.append(row)
        
        return ''.join(rows)
