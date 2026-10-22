name: Execute Seattle Road Closure Monitor

on:
  schedule:
    # Triggers every 15 minutes (GitHub's minimum allowed cron frequency)
    - cron: '*/15 * * * *'
  workflow_dispatch: # Allows you to press a button to manually force a test run

jobs:
  run-tracker:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code Repository State
        uses: actions/checkout@v4

      - name: Initialize Runtime Environment
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Extraction Script
        env:
          SDOT_API_KEY: ${{ secrets.SDOT_API_KEY }}
          DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}
        run: python bot.py

      - name: Commit and Persist Deduplication Log
        run: |
          git config --global user.name "ClosureBotRunner"
          git config --global user.email "bot@github.actions.internal"
          git add seen_ids.txt || true
          git commit -m "System auto-update: Appended newly observed event tracking tokens [skip ci]" || true
          git push || true
