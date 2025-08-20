{{/*
Expand the name of the chart.
*/}}
{{- define "canopyiq.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "canopyiq.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "canopyiq.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "canopyiq.labels" -}}
helm.sh/chart: {{ include "canopyiq.chart" . }}
{{ include "canopyiq.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.labels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "canopyiq.selectorLabels" -}}
app.kubernetes.io/name: {{ include "canopyiq.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "canopyiq.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "canopyiq.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use
*/}}
{{- define "canopyiq.secretName" -}}
{{- if .Values.secrets.secretName }}
{{- .Values.secrets.secretName }}
{{- else }}
{{- printf "%s-secret" (include "canopyiq.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Create the name of the configmap to use
*/}}
{{- define "canopyiq.configMapName" -}}
{{- printf "%s-config" (include "canopyiq.fullname" .) }}
{{- end }}

{{/*
Common annotations
*/}}
{{- define "canopyiq.annotations" -}}
{{- with .Values.annotations }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod annotations
*/}}
{{- define "canopyiq.podAnnotations" -}}
{{- with .Values.podAnnotations }}
{{ toYaml . }}
{{- end }}
{{- with .Values.annotations }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod labels
*/}}
{{- define "canopyiq.podLabels" -}}
{{ include "canopyiq.selectorLabels" . }}
{{- with .Values.podLabels }}
{{ toYaml . }}
{{- end }}
{{- with .Values.labels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Create image pull secrets
*/}}
{{- define "canopyiq.imagePullSecrets" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Generate the image name
*/}}
{{- define "canopyiq.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{/*
Create ingress hostname
*/}}
{{- define "canopyiq.ingressHost" -}}
{{- if .Values.ingress.hosts }}
{{- (index .Values.ingress.hosts 0).host }}
{{- else }}
{{- "canopyiq.local" }}
{{- end }}
{{- end }}

{{/*
ServiceMonitor namespace
*/}}
{{- define "canopyiq.serviceMonitorNamespace" -}}
{{- if .Values.monitoring.serviceMonitor.namespace }}
{{- .Values.monitoring.serviceMonitor.namespace }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
PodMonitor namespace
*/}}
{{- define "canopyiq.podMonitorNamespace" -}}
{{- if .Values.monitoring.podMonitor.namespace }}
{{- .Values.monitoring.podMonitor.namespace }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Create a default storage class name.
*/}}
{{- define "canopyiq.storageClassName" -}}
{{- if .Values.persistence.storageClass }}
{{- if (eq "-" .Values.persistence.storageClass) }}
storageClassName: ""
{{- else }}
storageClassName: {{ .Values.persistence.storageClass | quote }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Validate ingress configuration
*/}}
{{- define "canopyiq.validateIngress" -}}
{{- if and .Values.ingress.enabled (not .Values.ingress.hosts) }}
{{- fail "ingress.hosts must be specified when ingress is enabled" }}
{{- end }}
{{- end }}

{{/*
Validate autoscaling configuration
*/}}
{{- define "canopyiq.validateAutoscaling" -}}
{{- if and .Values.autoscaling.enabled (lt .Values.autoscaling.minReplicas .Values.replicaCount) }}
{{- fail "autoscaling.minReplicas must be greater than or equal to replicaCount when autoscaling is enabled" }}
{{- end }}
{{- end }}

{{/*
Create environment variables from values
*/}}
{{- define "canopyiq.envVars" -}}
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
Create environment variables from secrets
*/}}
{{- define "canopyiq.secretEnvVars" -}}
{{- $secretName := include "canopyiq.secretName" . }}
{{- range $envVar, $secretKey := .Values.secrets.keys }}
- name: {{ $envVar }}
  valueFrom:
    secretKeyRef:
      name: {{ $secretName }}
      key: {{ $secretKey }}
{{- end }}
{{- end }}

{{/*
Create environment variables from configmap
*/}}
{{- define "canopyiq.configMapEnvVars" -}}
{{- $configMapName := include "canopyiq.configMapName" . }}
{{- range $key, $value := .Values.configMap.data }}
- name: {{ $key }}
  valueFrom:
    configMapKeyRef:
      name: {{ $configMapName }}
      key: {{ $key }}
{{- end }}
{{- end }}