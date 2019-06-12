int forloop(int n) {
    for(int k=0;
        k<10;
        k++)
    {
        n = n * 2;
    }
    return n;
}

int main() {
    int x, y, n, m[2];
    if ((x >= 3) &&
        (y + 3 <= 6) &&
        (m[1] == m[2])) {
        n = 2;
    }
    n =
        n > 2 ?
                0 :
                    1;

    if (n) {
        n -= 1;
    }

    if (x) { y++; } else { y--;} n++;

    if (x)
    n++;

    if (y) {n++;} else {x++;};

    return forloop(n);
}
