#ifndef MATRIX_H
#define MATRIX_H

#include <stddef.h>
#include <string.h>
#include <math.h>

// 3x3 matrix operations
typedef struct {
    float data[3][3];
} mat3_t;

// 15x15 matrix operations
typedef struct {
    float data[15][15];
} mat15_t;

// 3D vector
typedef struct {
    float data[3];
} vec3_t;

// 15D vector for state
typedef struct {
    float data[15];
} vec15_t;

// 3x3 Matrix operations
void mat3_identity(mat3_t* m);
void mat3_zero(mat3_t* m);
void mat3_copy(mat3_t* dst, const mat3_t* src);
void mat3_multiply(mat3_t* result, const mat3_t* a, const mat3_t* b);
void mat3_multiply_vec3(vec3_t* result, const mat3_t* m, const vec3_t* v);
void mat3_add(mat3_t* result, const mat3_t* a, const mat3_t* b);
void mat3_subtract(mat3_t* result, const mat3_t* a, const mat3_t* b);
void mat3_scale(mat3_t* result, const mat3_t* m, float scalar);
void mat3_transpose(mat3_t* result, const mat3_t* m);
int mat3_inverse(mat3_t* result, const mat3_t* m);
void mat3_from_axis_angle(mat3_t* result, const vec3_t* axis_angle);
void mat3_to_euler(const mat3_t* m, float* roll, float* pitch, float* yaw);
void mat3_from_euler(mat3_t* m, float roll, float pitch, float yaw);

// 15x15 Matrix operations
void mat15_identity(mat15_t* m);
void mat15_zero(mat15_t* m);
void mat15_copy(mat15_t* dst, const mat15_t* src);
void mat15_multiply(mat15_t* result, const mat15_t* a, const mat15_t* b);
void mat15_add(mat15_t* result, const mat15_t* a, const mat15_t* b);
void mat15_scale(mat15_t* result, const mat15_t* m, float scalar);
void mat15_set_block_3x3(mat15_t* m, int row, int col, const mat3_t* block);
void mat15_get_block_3x3(const mat15_t* m, int row, int col, mat3_t* block);

// Vector operations
void vec3_zero(vec3_t* v);
void vec3_copy(vec3_t* dst, const vec3_t* src);
void vec3_add(vec3_t* result, const vec3_t* a, const vec3_t* b);
void vec3_subtract(vec3_t* result, const vec3_t* a, const vec3_t* b);
void vec3_scale(vec3_t* result, const vec3_t* v, float scalar);
float vec3_dot(const vec3_t* a, const vec3_t* b);
void vec3_cross(vec3_t* result, const vec3_t* a, const vec3_t* b);
float vec3_norm(const vec3_t* v);
void vec3_normalize(vec3_t* result, const vec3_t* v);

// Skew symmetric matrix
void mat3_skew(mat3_t* result, const vec3_t* v);

#endif // MATRIX_H