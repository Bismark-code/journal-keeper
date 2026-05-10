import { NextRequest, NextResponse } from "next/server";

const API_PORT = 3030;

async function proxyRequest(req: NextRequest) {
  const url = new URL(req.url);
  // Извлекаем путь после /api/
  const path = url.pathname.replace(/^\/api/, '');
  const searchParams = url.searchParams.toString();
  const targetUrl = `http://127.0.0.1:${API_PORT}/api${path}${searchParams ? '?' + searchParams : ''}`;

  try {
    const fetchOptions: RequestInit = {
      method: req.method,
    };

    const contentType = req.headers.get('Content-Type') || '';

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      if (contentType.includes('multipart/form-data')) {
        const formData = await req.formData();
        fetchOptions.body = formData;
      } else {
        fetchOptions.headers = { 'Content-Type': contentType };
        fetchOptions.body = await req.text();
      }
    }

    const res = await fetch(targetUrl, fetchOptions);
    const data = await res.text();

    const responseHeaders = new Headers();
    const resContentType = res.headers.get('Content-Type');
    if (resContentType) {
      responseHeaders.set('Content-Type', resContentType);
    }

    return new NextResponse(data, {
      status: res.status,
      headers: responseHeaders,
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: `API server error: ${error.message}` },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest) {
  return proxyRequest(req);
}

export async function POST(req: NextRequest) {
  return proxyRequest(req);
}

export async function PUT(req: NextRequest) {
  return proxyRequest(req);
}

export async function DELETE(req: NextRequest) {
  return proxyRequest(req);
}
