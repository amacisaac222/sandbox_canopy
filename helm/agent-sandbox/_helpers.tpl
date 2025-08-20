{{- define "agent-sandbox.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "agent-sandbox.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}