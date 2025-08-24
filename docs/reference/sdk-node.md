# SDK (Node.js / TypeScript)

```ts
import { Guard } from "@canopyiq/js";

const guard = new Guard({ policies: "policies/baseline.yaml" });

const res = await guard.check("file_write", { path: "/etc/passwd" });
if (res.allow) {
  await writeFile("/etc/passwd", "...");
} else if (res.approval_required) {
  await guard.requestApproval(res);
} else {
  console.log("Blocked:", res.reason);
}
```