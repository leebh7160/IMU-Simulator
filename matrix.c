#include "matrix.h"
#include <stdio.h>

// 3x3 Matrix operations
void mat3_identity(mat3_t* m) {
    memset(m->data, 0, sizeof(m->data));
    for (int i = 0; i < 3; i++) {
        m->data[i][i] = 1.0f;
    }
}

void mat3_zero(mat3_t* m) {
    memset(m->data, 0, sizeof(m->data));
}

void mat3_copy(mat3_t* dst, const mat3_t* src) {
    memcpy(dst->data, src->data, sizeof(src->data));
}

void mat3_multiply(mat3_t* result, const mat3_t* a, const mat3_t* b) {
    mat3_t temp;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            temp.data[i][j] = 0;
            for (int k = 0; k < 3; k++) {
                temp.data[i][j] += a->data[i][k] * b->data[k][j];
            }
        }
    }
    mat3_copy(result, &temp);
}

void mat3_multiply_vec3(vec3_t* result, const mat3_t* m, const vec3_t* v) {
    vec3_t temp;
    for (int i = 0; i < 3; i++) {
        temp.data[i] = 0;
        for (int j = 0; j < 3; j++) {
            temp.data[i] += m->data[i][j] * v->data[j];
        }
    }
    vec3_copy(result, &temp);
}

void mat3_add(mat3_t* result, const mat3_t* a, const mat3_t* b) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            result->data[i][j] = a->data[i][j] + b->data[i][j];
        }
    }
}

void mat3_subtract(mat3_t* result, const mat3_t* a, const mat3_t* b) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            result->data[i][j] = a->data[i][j] - b->data[i][j];
        }
    }
}

void mat3_scale(mat3_t* result, const mat3_t* m, float scalar) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            result->data[i][j] = m->data[i][j] * scalar;
        }
    }
}

void mat3_transpose(mat3_t* result, const mat3_t* m) {
    mat3_t temp;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            temp.data[i][j] = m->data[j][i];
        }
    }
    mat3_copy(result, &temp);
}

int mat3_inverse(mat3_t* result, const mat3_t* m) {
    float det = m->data[0][0] * (m->data[1][1] * m->data[2][2] - m->data[1][2] * m->data[2][1])
              - m->data[0][1] * (m->data[1][0] * m->data[2][2] - m->data[1][2] * m->data[2][0])
              + m->data[0][2] * (m->data[1][0] * m->data[2][1] - m->data[1][1] * m->data[2][0]);

    if (fabsf(det) < 1e-10f) {
        return 0; // Matrix is singular
    }

    float inv_det = 1.0f / det;
    mat3_t temp;

    temp.data[0][0] = (m->data[1][1] * m->data[2][2] - m->data[1][2] * m->data[2][1]) * inv_det;
    temp.data[0][1] = (m->data[0][2] * m->data[2][1] - m->data[0][1] * m->data[2][2]) * inv_det;
    temp.data[0][2] = (m->data[0][1] * m->data[1][2] - m->data[0][2] * m->data[1][1]) * inv_det;

    temp.data[1][0] = (m->data[1][2] * m->data[2][0] - m->data[1][0] * m->data[2][2]) * inv_det;
    temp.data[1][1] = (m->data[0][0] * m->data[2][2] - m->data[0][2] * m->data[2][0]) * inv_det;
    temp.data[1][2] = (m->data[0][2] * m->data[1][0] - m->data[0][0] * m->data[1][2]) * inv_det;

    temp.data[2][0] = (m->data[1][0] * m->data[2][1] - m->data[1][1] * m->data[2][0]) * inv_det;
    temp.data[2][1] = (m->data[0][1] * m->data[2][0] - m->data[0][0] * m->data[2][1]) * inv_det;
    temp.data[2][2] = (m->data[0][0] * m->data[1][1] - m->data[0][1] * m->data[1][0]) * inv_det;

    mat3_copy(result, &temp);
    return 1;
}

void mat3_from_axis_angle(mat3_t* result, const vec3_t* axis_angle) {
    float angle = vec3_norm(axis_angle);

    if (angle < 1e-12f) {
        mat3_identity(result);
        return;
    }

    vec3_t axis;
    vec3_scale(&axis, axis_angle, 1.0f / angle);

    float c = cosf(angle);
    float s = sinf(angle);
    float t = 1.0f - c;

    float x = axis.data[0];
    float y = axis.data[1];
    float z = axis.data[2];

    result->data[0][0] = t*x*x + c;
    result->data[0][1] = t*x*y - s*z;
    result->data[0][2] = t*x*z + s*y;

    result->data[1][0] = t*x*y + s*z;
    result->data[1][1] = t*y*y + c;
    result->data[1][2] = t*y*z - s*x;

    result->data[2][0] = t*x*z - s*y;
    result->data[2][1] = t*y*z + s*x;
    result->data[2][2] = t*z*z + c;
}

void mat3_to_euler(const mat3_t* m, float* roll, float* pitch, float* yaw) {
    *pitch = asinf(-m->data[2][0]);

    if (cosf(*pitch) > 1e-6f) {
        *roll = atan2f(m->data[2][1], m->data[2][2]);
        *yaw = atan2f(m->data[1][0], m->data[0][0]);
    } else {
        *roll = 0;
        *yaw = atan2f(-m->data[0][1], m->data[1][1]);
    }
}

void mat3_from_euler(mat3_t* m, float roll, float pitch, float yaw) {
    float cr = cosf(roll), sr = sinf(roll);
    float cp = cosf(pitch), sp = sinf(pitch);
    float cy = cosf(yaw), sy = sinf(yaw);

    m->data[0][0] = cy * cp;
    m->data[0][1] = cy * sp * sr - sy * cr;
    m->data[0][2] = cy * sp * cr + sy * sr;

    m->data[1][0] = sy * cp;
    m->data[1][1] = sy * sp * sr + cy * cr;
    m->data[1][2] = sy * sp * cr - cy * sr;

    m->data[2][0] = -sp;
    m->data[2][1] = cp * sr;
    m->data[2][2] = cp * cr;
}

// 15x15 Matrix operations
void mat15_identity(mat15_t* m) {
    memset(m->data, 0, sizeof(m->data));
    for (int i = 0; i < 15; i++) {
        m->data[i][i] = 1.0f;
    }
}

void mat15_zero(mat15_t* m) {
    memset(m->data, 0, sizeof(m->data));
}

void mat15_copy(mat15_t* dst, const mat15_t* src) {
    memcpy(dst->data, src->data, sizeof(src->data));
}

void mat15_multiply(mat15_t* result, const mat15_t* a, const mat15_t* b) {
    mat15_t temp;
    for (int i = 0; i < 15; i++) {
        for (int j = 0; j < 15; j++) {
            temp.data[i][j] = 0;
            for (int k = 0; k < 15; k++) {
                temp.data[i][j] += a->data[i][k] * b->data[k][j];
            }
        }
    }
    mat15_copy(result, &temp);
}

void mat15_add(mat15_t* result, const mat15_t* a, const mat15_t* b) {
    for (int i = 0; i < 15; i++) {
        for (int j = 0; j < 15; j++) {
            result->data[i][j] = a->data[i][j] + b->data[i][j];
        }
    }
}

void mat15_scale(mat15_t* result, const mat15_t* m, float scalar) {
    for (int i = 0; i < 15; i++) {
        for (int j = 0; j < 15; j++) {
            result->data[i][j] = m->data[i][j] * scalar;
        }
    }
}

void mat15_set_block_3x3(mat15_t* m, int row, int col, const mat3_t* block) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            m->data[row + i][col + j] = block->data[i][j];
        }
    }
}

void mat15_get_block_3x3(const mat15_t* m, int row, int col, mat3_t* block) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            block->data[i][j] = m->data[row + i][col + j];
        }
    }
}

// Vector operations
void vec3_zero(vec3_t* v) {
    memset(v->data, 0, sizeof(v->data));
}

void vec3_copy(vec3_t* dst, const vec3_t* src) {
    memcpy(dst->data, src->data, sizeof(src->data));
}

void vec3_add(vec3_t* result, const vec3_t* a, const vec3_t* b) {
    for (int i = 0; i < 3; i++) {
        result->data[i] = a->data[i] + b->data[i];
    }
}

void vec3_subtract(vec3_t* result, const vec3_t* a, const vec3_t* b) {
    for (int i = 0; i < 3; i++) {
        result->data[i] = a->data[i] - b->data[i];
    }
}

void vec3_scale(vec3_t* result, const vec3_t* v, float scalar) {
    for (int i = 0; i < 3; i++) {
        result->data[i] = v->data[i] * scalar;
    }
}

float vec3_dot(const vec3_t* a, const vec3_t* b) {
    float result = 0;
    for (int i = 0; i < 3; i++) {
        result += a->data[i] * b->data[i];
    }
    return result;
}

void vec3_cross(vec3_t* result, const vec3_t* a, const vec3_t* b) {
    vec3_t temp;
    temp.data[0] = a->data[1] * b->data[2] - a->data[2] * b->data[1];
    temp.data[1] = a->data[2] * b->data[0] - a->data[0] * b->data[2];
    temp.data[2] = a->data[0] * b->data[1] - a->data[1] * b->data[0];
    vec3_copy(result, &temp);
}

float vec3_norm(const vec3_t* v) {
    return sqrtf(v->data[0] * v->data[0] +
                 v->data[1] * v->data[1] +
                 v->data[2] * v->data[2]);
}

void vec3_normalize(vec3_t* result, const vec3_t* v) {
    float norm = vec3_norm(v);
    if (norm > 1e-12f) {
        vec3_scale(result, v, 1.0f / norm);
    } else {
        vec3_zero(result);
    }
}

void mat3_skew(mat3_t* result, const vec3_t* v) {
    result->data[0][0] = 0;
    result->data[0][1] = -v->data[2];
    result->data[0][2] = v->data[1];

    result->data[1][0] = v->data[2];
    result->data[1][1] = 0;
    result->data[1][2] = -v->data[0];

    result->data[2][0] = -v->data[1];
    result->data[2][1] = v->data[0];
    result->data[2][2] = 0;
}