import os
import yaml
from datetime import datetime
from .. import config
from urllib.parse import unquote

def generate_html_report(app, env, tags, start_time, results, results_by_file, base_url):
    """
    Generate an HTML report for API test results.
    """
    total_tests = len(results)
    passed = sum(1 for r in results.values() if r['status'])
    failed = total_tests - passed
    skipped = total_tests - passed - failed
    pass_rate = (passed/total_tests)*100 if total_tests > 0 else 0
    tags_str = ", ".join(tags) if tags else "-"

    end_time = datetime.now()
    duration = end_time - start_time
    report_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
    report_filename = f"{app}_test_report.html"

    # Ensure reports directory exists under api_testing package
    base_pkg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    reports_dir = os.path.join(base_pkg_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    report_filepath = os.path.join(reports_dir, report_filename)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>{app} API Test Report</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 10px; }}
      .summary-table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
      .summary-table th, .summary-table td {{ border: 1px solid #ddd; padding: 6px; text-align: left; font-size: 12px; }}
      .summary-table th {{ background-color: #e6f7ff; }}
      .details-table {{ border-collapse: collapse; width: 100%; margin-top: 20px; margin-bottom: 10px; table-layout: fixed; }}
      .details-table th, .details-table td {{ border: 1px solid #ddd; padding: 6px; font-size: 14px; text-align: left; font-family: 'Times New Roman', serif; }}
      .details-table th {{ background-color: #e6f7ff; }}
      /* fixed widths for description and request details columns */
      .details-table th:nth-child(1), .details-table td:nth-child(1) {{
        /* fixed width for description */
        width: 300px;
        word-wrap: break-word;
      }}
      .details-table th:nth-child(2), .details-table td:nth-child(2) {{
        /* fixed width for request details */
        width: 650px;
        word-wrap: break-word;
      }}
      /* fixed width for status column */
      .details-table th:nth-child(3), .details-table td:nth-child(3) {{
        width: 50px;
        min-width: 50px;
        max-width: 50px;
        text-align: center;
      }}
      summary {{ font-weight: bold; cursor: pointer; font-family: 'Times New Roman', serif; font-size: 14px; }}
      .summary-metrics {{ font-size: 16px; }}
      .file-name {{ font-size: 16px; }}
      details {{
        margin: 10px 0;
        padding: 10px;
        border-radius: 5px;
        background: linear-gradient(135deg, #f9f9f9, #e0e0e0);
      }}
      details[open] {{
        background-color: #fff;
      }}
      ul {{ list-style-type: none; padding-left: 20px; }}
      .pass {{ color: green; }}
      .fail {{ color: red; }}
      .metric-total {{ color: darkblue; font-size: 10px; }}
      .metric-passed {{ color: green; font-size: 10px; }}
      .metric-failed {{ color: red; font-size: 10px; }}
      .metric-skipped {{ color: #C9A640; font-size: 10px; }}
      .filter-container {{ margin: 20px 0; margin-left: 20px;}}
      .filter-container label {{ margin-right: 10px; }}
      .filter-container label.passed {{ color: green; }}
      .filter-container label.failed {{ color: red; }}
      .filter-container label.skipped {{ color: #C9A640; }}
      .summary-container {{ display: flex; width: 100%; margin: 0 0 20px 0; gap: 20px; }}
      .summary-details, .summary-summary {{ flex: 1; }}
      .summary-chart {{ flex: 0 0 40%; max-width: 40%; display: flex; flex-direction: column; align-items: center; margin-top: auto; }}
      .chart-total {{ font-size: 14px; margin-top: 5px; text-align: center; }}
      /* Style expanded Base URL separately from table */
      details[open] > p {{
        background: linear-gradient(135deg, #f9f9f9, #e0e0e0);
        padding: 6px;
        border-radius: 3px;
      }}
      details[open] > table.details-table {{
        background-color: #fff;
      }}
    </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
</head>
<body>
  <h1>API Test Report: {app}</h1>
  <div class="summary-container">
    <div class="summary-details">
      <h3>Execution Details</h3>
      <table class="summary-table" style="margin-left: 20px;">
        <thead><tr><th>Detail</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td>Application</td><td>{app}</td></tr>
          <tr><td>Environment</td><td>{env}</td></tr>
          <tr><td>Tags</td><td>{tags_str}</td></tr>
          <tr><td>Started at</td><td>{report_time}</td></tr>
          <tr><td>Duration</td><td>{duration}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="summary-summary">
      <h3>Execution Summary</h3>
      <table class="summary-table" style="margin-left: 20px;">
        <thead><tr><th>Metric</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td>Total Testcases</td><td>{total_tests}</td></tr>
          <tr><td>Passed</td><td>{passed}</td></tr>
          <tr><td>Failed</td><td>{failed}</td></tr>
          <tr><td>Skipped</td><td>{skipped}</td></tr>
          <tr><td>Pass Rate</td><td>{pass_rate:.1f}%</td></tr>
        </tbody>
      </table>
    </div>
    <div class="summary-chart">
      <canvas id="pieChart" width="150" height="150"></canvas>
      <p class="chart-total">Total testcases: {total_tests}</p>
    </div>
  </div>
  <div class='filter-container'>
    <label class='passed'><input type='checkbox' id='filter-passed' checked> Show Passed</label>
    <label class='failed'><input type='checkbox' id='filter-failed' checked> Show Failed</label>
    <label class='skipped'><input type='checkbox' id='filter-skipped' checked> Show Skipped</label>
  </div>
  <script>
    function applyFilters() {{
      var showPassed = document.getElementById('filter-passed').checked;
      var showFailed = document.getElementById('filter-failed').checked;
      var showSkipped = document.getElementById('filter-skipped').checked;
      document.querySelectorAll('.details-table tbody tr').forEach(function(row) {{
        if (row.classList.contains('pass')) row.style.display = showPassed ? '' : 'none';
        else if (row.classList.contains('fail')) row.style.display = showFailed ? '' : 'none';
        else row.style.display = showSkipped ? '' : 'none';
      }});
    }}
    document.getElementById('filter-passed').addEventListener('change', applyFilters);
    document.getElementById('filter-failed').addEventListener('change', applyFilters);
    document.getElementById('filter-skipped').addEventListener('change', applyFilters);
    function initChart() {{
      // register DataLabels plugin
      Chart.register(ChartDataLabels);
      const ctx = document.getElementById('pieChart').getContext('2d');
      new Chart(ctx, {{
        type: 'pie',
        data: {{ labels: ['Passed','Failed','Skipped'], datasets: [{{ data: [{passed},{failed},{skipped}], backgroundColor: ['#28a745','#dc3545','#C9A640'] }}] }},
        options: {{
          responsive: false,
          plugins: {{
            legend: {{ display: false }},
            datalabels: {{
              color: '#fff',
              display: (ctx) => ctx.dataset.data[ctx.dataIndex] > 0,
              formatter: (value, ctx) => {{
                let sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                return (value/sum*100).toFixed(1) + '%';
              }}
            }}
          }}
        }}
      }});
    }}
    window.onload = function() {{ applyFilters(); initChart(); }};
  </script>
  <h2>Details</h2>
"""
    # Append details per file
    skipped_files = []
    for test_file, file_results in results_by_file.items():
        tests_dir = str(config.TESTS_BASE_DIR)
        relpath = os.path.relpath(test_file, tests_dir)
        try:
            with open(test_file) as tf:
                data = yaml.safe_load(tf)
                raw_cases = data.get('test_cases', data if isinstance(data, list) else [])
        except Exception:
            raw_cases = []
        total_file = len(raw_cases)
        passed_file = sum(1 for r in file_results.values() if r['status'])
        failed_file = sum(1 for r in file_results.values() if not r['status'])
        skipped_file = total_file - (passed_file + failed_file)
        # Collect fully skipped files
        if total_file > 0 and skipped_file == total_file:
            skipped_files.append((relpath, total_file))
            continue
        html += f"<details><summary><span class=\"file-name\">tests/{relpath}</span> <span class=\"summary-metrics\">[<span class=\"metric-total\">Total: {total_file}</span>, <span class=\"metric-passed\">Passed: {passed_file}</span>, <span class=\"metric-failed\">Failed: {failed_file}</span>, <span class=\"metric-skipped\">Skipped: {skipped_file}</span>]</span></summary>"
        html += f'<p style="font-size: 13px;"><strong>Base URL:</strong> {base_url}</p>'
        html += "<table class=\"details-table\"><thead><tr><th>Description</th><th>Request Details</th><th>Status</th><th>Notes</th></tr></thead><tbody>"
        for test_name, result in file_results.items():
            try:
                with open(test_file) as tf:
                    data = yaml.safe_load(tf)
                    cases = data.get('test_cases', data if isinstance(data, list) else [])
                    case = next((c for c in cases if c.get('name') == test_name), {})
                    description = case.get('description') or test_name
                    # Use full resolved request URL (with base_url) and decode
                    url = unquote(result.get('request_url', ''))
            except Exception:
                description = ''
                url = ''
            status_icon = '&#10004;' if result['status'] else '&#10008;'
            notes = '' if result['status'] else result.get('error', '')
            status_class = 'pass' if result['status'] else 'fail'
            html += f"<tr class=\"{status_class}\"><td>{description}</td><td>{url}<br><strong>Data:</strong> {result.get('request_data', {})}</td><td>{status_icon}</td><td>{notes}</td></tr>"
        html += "</tbody></table></details>\n"
    # Section for files where all testcases were skipped
    if skipped_files:
        html += "<h2>Skipped Files</h2>\n<ul>\n"
        for rel, total in skipped_files:
            html += f"<li>tests/{rel} (Total: {total})</li>\n"
        html += "</ul>\n"
    # Close HTML
    html += "</body></html>"

    with open(report_filepath, 'w') as f:
        f.write(html)

    print(f"HTML report generated: {report_filepath}")
