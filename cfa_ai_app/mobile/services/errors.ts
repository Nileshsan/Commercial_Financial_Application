import { AxiosError } from 'axios';

export class NetworkError extends Error {
  constructor(message: string, public originalError?: AxiosError) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public response?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class AuthenticationError extends Error {
  constructor(message: string = 'Authentication failed') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class OfflineError extends Error {
  constructor(message: string = 'No internet connection') {
    super(message);
    this.name = 'OfflineError';
  }
}
