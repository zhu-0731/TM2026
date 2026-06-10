# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM --platform=$BUILDPLATFORM golang:1.23.4-alpine@sha256:c23339199a08b0e12032856908589a6d41a0dab141b8b3b21f156fc571a3f1d3 AS builder
ARG TARGETOS
ARG TARGETARCH
WORKDIR /src

# restore dependencies
COPY go.mod go.sum ./
RUN go mod download

# 显式复制每个文件，确保新代码一定被复制进去
COPY main.go .
COPY handlers.go .
COPY rpc.go .
COPY middleware.go .
COPY deployment_details.go .
COPY packaging_info.go .
COPY go.mod .
COPY go.sum .
COPY ./templates ./templates
COPY ./static ./static
COPY ./money ./money
COPY ./genproto ./genproto
COPY ./validator ./validator

# 验证代码是否包含最新修改
RUN grep -q "COUPON SUPPORT" main.go && echo "CODE IS FRESH" || (echo "CODE IS STALE" && exit 1)
RUN grep -q "DEBUG header" handlers.go && echo "HANDLERS IS FRESH" || (echo "HANDLERS IS STALE" && exit 1)

# Skaffold passes in debug-oriented compiler flags
ARG SKAFFOLD_GO_GCFLAGS
RUN GOOS=${TARGETOS} GOARCH=${TARGETARCH} CGO_ENABLED=0 go build -gcflags="${SKAFFOLD_GO_GCFLAGS}" -o /go/bin/frontend .

FROM scratch
WORKDIR /src
COPY --from=builder /go/bin/frontend /src/server
COPY ./templates ./templates
COPY ./static ./static

# Definition of this variable is used by 'skaffold debug' to identify a golang binary.
# Default behavior - a failure prints a stack trace for the current goroutine.
# See https://golang.org/pkg/runtime/
ENV GOTRACEBACK=single

EXPOSE 8080
ENTRYPOINT ["/src/server"]
