# FAQ

**Will this slow agents down?**  
Policies evaluate in **<10ms**. Approvals add human latency only when needed.

**Do we need to rewrite agents?**  
No. Use the SDK or run as a proxy layer.

**Can it run offline?**  
Yes. Signed policy bundles allow offline enforcement.

**Where are logs stored?**  
In your infra (Postgres/S3). You control retention and export.