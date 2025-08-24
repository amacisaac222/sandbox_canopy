# Tutorial: Forward Logs to Splunk

1. Configure HEC token & URL in `CANOPYIQ_SPLUNK_HEC_*`.
2. Enable Splunk sink in `config.yaml`.
3. Verify events:
   - index: `canopyiq`
   - sourcetype: `canopyiq:audit`