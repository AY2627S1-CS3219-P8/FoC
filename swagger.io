swagger: "2.0"
info:
  title: FoC User Service API
  description: |
    API contract for user registration, authentication, session management,
    and profile access in Friend on Campus.
  version: "1.0.0"
host: localhost:8080
basePath: /
schemes:
  - http
consumes:
  - application/json
produces:
  - application/json

securityDefinitions:
  bearerAuth:
    type: apiKey
    name: Authorization
    in: header
    description: Use the format `Bearer <access_token>`.

paths:
  /health:
    get:
      summary: Check service liveness
      operationId: healthCheck
      responses:
        "200":
          description: Service is healthy.
          schema:
            $ref: '#/definitions/StatusResponse'

  /ready:
    get:
      summary: Check service readiness
      operationId: readinessCheck
      responses:
        "200":
          description: Service is ready and can access its database.
          schema:
            $ref: '#/definitions/StatusResponse'
        "503":
          description: Database is unavailable.
          schema:
            $ref: '#/definitions/ErrorResponse'

  /users:
    post:
      summary: Register a user account
      operationId: createUser
      parameters:
        - in: body
          name: user
          required: true
          schema:
            $ref: '#/definitions/UserCreate'
      responses:
        "201":
          description: User account created.
          schema:
            $ref: '#/definitions/UserResponse'
        "409":
          description: The email address or NUS student number is already in use.
          schema:
            $ref: '#/definitions/ErrorResponse'
        "422":
          description: Request validation failed.
          schema:
            $ref: '#/definitions/ValidationErrorResponse'
        "503":
          description: Database is temporarily unavailable.
          schema:
            $ref: '#/definitions/ErrorResponse'

  /login:
    post:
      summary: Authenticate a user
      operationId: login
      parameters:
        - in: body
          name: credentials
          required: true
          schema:
            $ref: '#/definitions/UserLogin'
      responses:
        "200":
          description: Authentication succeeded.
          schema:
            $ref: '#/definitions/LoginResponse'
        "401":
          description: Credentials are invalid or the account is inactive.
          schema:
            $ref: '#/definitions/ErrorResponse'
        "422":
          description: Request validation failed.
          schema:
            $ref: '#/definitions/ValidationErrorResponse'
        "503":
          description: Database or authentication storage is temporarily unavailable.
          schema:
            $ref: '#/definitions/ErrorResponse'

  /logout:
    post:
      summary: Revoke the current session
      operationId: logout
      security:
        - bearerAuth: []
      responses:
        "204":
          description: Session revoked.
        "401":
          description: Bearer credentials are missing or invalid.
          schema:
            $ref: '#/definitions/ErrorResponse'
        "503":
          description: Authentication storage is temporarily unavailable.
          schema:
            $ref: '#/definitions/ErrorResponse'

  /users/me:
    get:
      summary: Get the authenticated user's profile
      operationId: getCurrentUser
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Authenticated user's non-sensitive profile.
          schema:
            $ref: '#/definitions/UserResponse'
        "401":
          description: Bearer credentials are missing or invalid.
          schema:
            $ref: '#/definitions/ErrorResponse'
        "503":
          description: Authentication storage is temporarily unavailable.
          schema:
            $ref: '#/definitions/ErrorResponse'

definitions:
  UserCreate:
    type: object
    additionalProperties: false
    required:
      - nus_student_number
      - email
      - display_name
      - password
    properties:
      nus_student_number:
        type: string
        description: NUS student number in the format A1234567B or U1234567B.
        pattern: '^[AaUu][0-9]{7}[A-Za-z]$'
        minLength: 9
        maxLength: 9
        example: A1234567B
      email:
        type: string
        format: email
        example: student@example.com
      display_name:
        type: string
        minLength: 1
        maxLength: 100
        example: Alex Tan
      password:
        type: string
        format: password
        description: 8–100 characters containing a letter, number, and special character.
        minLength: 8
        maxLength: 100
        example: Campus!123

  UserLogin:
    type: object
    additionalProperties: false
    required:
      - nus_student_number
      - password
    properties:
      nus_student_number:
        type: string
        pattern: '^[AaUu][0-9]{7}[A-Za-z]$'
        minLength: 9
        maxLength: 9
        example: A1234567B
      password:
        type: string
        format: password
        minLength: 1
        maxLength: 100
        example: Campus!123

  UserResponse:
    type: object
    required:
      - id
      - nus_student_number
      - email
      - display_name
      - role
      - status
      - created_at
      - updated_at
    properties:
      id:
        type: string
        format: uuid
      nus_student_number:
        type: string
      email:
        type: string
        format: email
      display_name:
        type: string
      role:
        type: string
        enum:
          - user
          - admin
      status:
        type: string
        enum:
          - active
          - deactivated
          - suspended
      created_at:
        type: string
        format: date-time
      updated_at:
        type: string
        format: date-time

  LoginResponse:
    type: object
    required:
      - access_token
      - token_type
      - expires_in
      - user
    properties:
      access_token:
        type: string
        description: Opaque bearer token. Store it securely and send it in the Authorization header.
        pattern: '^[A-Za-z0-9_-]{20,256}$'
      token_type:
        type: string
        enum:
          - bearer
      expires_in:
        type: integer
        format: int32
        description: Inactivity lifetime in seconds.
        example: 1800
      user:
        $ref: '#/definitions/UserResponse'

  StatusResponse:
    type: object
    required:
      - status
    properties:
      status:
        type: string
        example: healthy

  ErrorResponse:
    type: object
    required:
      - detail
    properties:
      detail:
        type: string

  ValidationErrorResponse:
    type: object
    required:
      - detail
    properties:
      detail:
        type: array
        items:
          type: object
          properties:
            loc:
              type: array
              items:
                type: string
            msg:
              type: string
            type:
              type: string
